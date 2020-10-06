"""This module integrates volcanic aerosols into konrad based on observational data
(CMIP6 dataset (e.g. Thomason et al., 2018), Pinatubo eruption, loading between 23 S 
and 23 N). They can be used either in the RCE simulations or simply for radiative 
flux or heating rate calculations.
The default setting is excluding volcanic aerosols.

**In an RCE simulation**

Create an instance of a aerosol class,  
create an appropriate radiation model, and run an RCE simulation.
    >>> import konrad
    >>> aerosol = konrad.aerosol.VolcanoAerosol(
    >>>     atmNumlevels=numlevels, aerosolLevelShiftInput=...,includeSWForcing=..,
    >>>     includeLWForcing=...,includeScattering=...,includeAbsorption=...,
    >>>     )
    >>> rce = konrad.RCE(atmosphere=..., aerosol=aerosol)
    >>> rce.run()

**Calculating radiative fluxes or heating rates**

Create an instance of a cloud class, *e.g.* a :py:class:`PhysicalCloud`,
create an appropriate radiation model and run radiative transfer.
    >>> import konrad
    >>> numlevels=200
    >>> plev, phlev = konrad.utils.get_pressure_grids(1000e2, 1,numlevels)
    >>> atmosphere = konrad.atmosphere.Atmosphere(plev)
    >>> aerosol = konrad.aerosol.VolcanoAerosol(
    >>>     atmNumlevels=numlevels, aerosolLevelShiftInput=...,includeSWForcing=..,
    >>>     includeLWForcing=...,includeScattering=...,includeAbsorption=...,
    >>>     )
    >>> rrtmg.calc_radiation(atmosphere, surface=...,volcanoAerosol) 
    
The aerosol class has a set of parameters:
    atmNumLevels: the number of pressure levels set for the atmosphere, also 
                    referred to as numlevels
    aerosol_type: choose between 'no_aerosol' for no volcanic aerosols
                                 'all_aerosol_properties' for volcanic aerosols,
                                      described by LW (ext) and SW (ext, g, ssa)
                                  'ecmwf' for volcanic aerosols, described by LW
                                      (ext) and SW (ext at 550 mu m) (currently
                                      not implemented in version available online)
    aerosolLevelShiftInput: choose the shift of the aerosol layer relative to the
                         original Pinatubo aerosol layer (units in km)
    monthsAfterEruption: chose the forcing data to describe the aerosol characteristics
                         x months after the eruption. Mount Pinatubo erupted on June 15, 1991.
                         allowed inputs in [0,18]
                         the input starts at 1 (July 1991).
                         Default value 2 is August 1991.
                         xxx not implemented yet xxxx 
    includeSWForcing: if True: imports the SW forcing files and calculates the radiative
                         fluxes using them
    includeScattering: includes SW scattering component
                        (only for 'all_aerosol_properties')
    includeAbsorption: includes SW absorption component
                        (only for 'all_aerosol_properties')
    includeLWForcing: if True: imports the LW forcing files and calculates the radiative
                         fluxes using them
"""
 
import os
import abc
import xarray as xr
import scipy as sc
import numpy as np
import typhon.physics as ty

from konrad.cloud import get_waveband_data_array
from konrad.cloud import get_aerosol_waveband_data_array




class Aerosol(metaclass=abc.ABCMeta):
    def __init__(self,atmNumlevels, aerosol_type='no_aerosol',monthsAfterEruption=8, aerosolLevelShiftInput=0,includeSWForcing=True,\
                 includeLWForcing=True,includeScattering=True,includeAbsorption=True):
         
        self._aerosol_type = aerosol_type
        self.includeSWForcing=includeSWForcing
        self.includeLWForcing=includeLWForcing
        self.aerosolLevelShift=aerosolLevelShiftInput
        self.monthsAfterEruption=monthsAfterEruption
        self.includeScattering=includeScattering
        self.includeAbsorption=includeAbsorption
        self.optical_thickness_due_to_aerosol_sw = \
            get_aerosol_waveband_data_array(0, units='dimensionless', numlevels=atmNumlevels, sw=True)   #called ext_sun in files
        self.single_scattering_albedo_aerosol_sw = \
            get_aerosol_waveband_data_array(0, units='dimensionless', numlevels=atmNumlevels, sw=True) #called omega_sun in files
        self.asymmetry_factor_aerosol_sw =  \
            get_aerosol_waveband_data_array(0, units='dimensionless', numlevels=atmNumlevels, sw=True)  #called g_sun in files
        self.optical_thickness_due_to_aerosol_lw = \
            get_aerosol_waveband_data_array(0, units='dimensionless', numlevels=atmNumlevels, sw=False) #called ext_earth in files

    #################################################################
    #To do: 
    #- time step updating
    #  For now the aerosols are left constant and are not updated
    #- implementation for a changing lapse rate, for now it is implemented only for a fixed lapse rate
    #- add the cold point as an output
    ################################################################
    def update_aerosols(self, time, atmosphere):
        return
    
    def calculateHeightLevels(self, atmosphere):
        return


class VolcanoAerosol(Aerosol):
    '''
    CMIP6 volcanic aerosols (Mount Pinatubo eruption)
    '''
    def __init__(self,atmNumlevels, monthsAfterEruption, aerosolLevelShiftInput=0,includeSWForcing=True,\
                 includeLWForcing=True,includeScattering=True,includeAbsorption=True):
        super().__init__(atmNumlevels,aerosol_type='all_aerosol_properties')
        self.aerosolLevelShift=aerosolLevelShiftInput
        self.monthsAfterEruption=monthsAfterEruption
        self.numlevels=atmNumlevels
        self.includeSWForcing=includeSWForcing
        self.includeLWForcing=includeLWForcing
        self.includeScattering=includeScattering
        self.includeAbsorption=includeAbsorption

    def update_aerosols(self, time, atmosphere):
        '''
        Import the volcanic forcing data in first time step, taking into account
        the parameter settings of the VolcanoAerosol class.
        Translate from height dependance to pressure dependance.
        The aerosol layer is kept fixed and constant throughout the following run.
        '''
        if not np.count_nonzero(self.optical_thickness_due_to_aerosol_sw.values):
            if self.includeLWForcing:
                extEarth = xr.open_dataset(
                        os.path.join(
                                os.path.dirname(__file__),
                                #'data/aerosolData/23dataextEarth1991.nc'
                                #'data/aerosolData/23dataextEarth1992.nc'
                                #'data/aerosolData/eva/23data10extEarthOrder.nc'
                                 'data/aerosolData/eva/23Tdata10extEarthOrder.nc'
                                ))
            if self.includeSWForcing:
                extSun = xr.open_dataset(
                        os.path.join(
                                os.path.dirname(__file__),
                                #'data/aerosolData/23dataextSun1991.nc'
                                #'data/aerosolData/23dataextSun1992.nc'
                                #'data/aerosolData/eva/23data10extSunOrder.nc'
                                 'data/aerosolData/eva/23Tdata10extSunOrder.nc'
                                ))
                gSun = xr.open_dataset(
                        os.path.join(
                                os.path.dirname(__file__),
                                #'data/aerosolData/23datagSun1991.nc'
                                #'data/aerosolData/23datagSun1992.nc'
                                #'data/aerosolData/eva/23data10gSunOrder.nc'
                                'data/aerosolData/eva/23Tdata10gSunOrder.nc'
                                ))
                omegaSun = xr.open_dataset(
                        os.path.join(
                                os.path.dirname(__file__),
                                #'data/aerosolData/23dataomegaSun1991.nc'
                                #'data/aerosolData/23dataomegaSun1992.nc'
                                #'data/aerosolData/eva/23data10omegaSunOrder.nc'
                                'data/aerosolData/eva/23Tdata10omegaSunOrder.nc'
                                ))
            heights = self.calculateHeightLevels(atmosphere)
            #the input data has to be scaled to fit to model levels
            #for compatability with rrtmg input format
            scaling=np.gradient(heights)
            
            if self.aerosolLevelShift:
 
                if self.includeLWForcing:
                    self.aerosolLevelShiftArray=self.aerosolLevelShift*np.ones(np.shape(extEarth.altitude[:]))
                    extEarth.altitude.values=extEarth.altitude.values+self.aerosolLevelShiftArray
                if self.includeSWForcing:
                    self.aerosolLevelShiftArray=self.aerosolLevelShift*np.ones(np.shape(extSun.altitude[:]))
                    extSun.altitude.values=extSun.altitude.values+self.aerosolLevelShiftArray
                    gSun.altitude.values=gSun.altitude.values+self.aerosolLevelShiftArray
                    omegaSun.altitude.values=omegaSun.altitude.values+self.aerosolLevelShiftArray
            
            if self.includeLWForcing:
                for lw_band in range(np.shape(extEarth.terrestrial_bands)[0]):
                    self.optical_thickness_due_to_aerosol_lw[lw_band, :] = \
                        sc.interpolate.interp1d(
                            extEarth.altitude.values,
                            extEarth.ext_earth[self.monthsAfterEruption,lw_band, :].values,
                            #extEarth.ext_earth[lw_band, :, 1].values,
                            bounds_error=False,
                            fill_value=0)(heights)*scaling
                        
            if self.includeSWForcing:
                for sw_band in range(np.shape(extSun.solar_bands)[0]):
                    self.optical_thickness_due_to_aerosol_sw[sw_band, :] = \
                        sc.interpolate.interp1d(
                            extSun.altitude.values,
                            extSun.ext_sun[sw_band,self.monthsAfterEruption, :].values,
                            #extSun.ext_sun[sw_band, :, 1],
                            bounds_error=False,
                            fill_value=0)(heights)*scaling
                    self.asymmetry_factor_aerosol_sw[sw_band, :] = \
                        sc.interpolate.interp1d(
                            gSun.altitude.values,
                            gSun.g_sun[sw_band,self.monthsAfterEruption, :].values,
                            #gSun.g_sun[sw_band, :, 1].values,
                            bounds_error=False,
                            fill_value=0)(heights)
                    self.single_scattering_albedo_aerosol_sw[sw_band, :] = \
                        sc.interpolate.interp1d(
                            omegaSun.altitude.values,
                            omegaSun.omega_sun[sw_band,self.monthsAfterEruption, :].values,
                            #omegaSun.omega_sun[sw_band, :, 1].values,
                            bounds_error=False,
                            fill_value=0)(heights)
 
                if not self.includeScattering: 
                    '''only absorption
                        SSA'=0, Omega'=Omega,Ext'=Ext*(1-SSA)'''
                    try:
                        a=get_aerosol_waveband_data_array(1, units='dimensionless', numlevels=self.numlevels, sw=True)
                        result= np.multiply(self.optical_thickness_due_to_aerosol_sw, \
                                            np.subtract(a,self.single_scattering_albedo_aerosol_sw)),
                                            
                        self.optical_thickness_due_to_aerosol_sw= \
                                get_aerosol_waveband_data_array(result[0].values.T, units='dimensionless', numlevels=self.numlevels, sw=True)
                        self.single_scattering_albedo_aerosol_sw = \
                                get_aerosol_waveband_data_array(0, units='dimensionless', numlevels=self.numlevels, sw=True) 
                        if not self.includeAbsorption:
                            raise ValueError('For aerosols scattering and absorption can not both be deactivated')
                    except (ValueError):
                        exit('Please choose valid input data.')
                        
                if not self.includeAbsorption: 
                    '''only scattering
                        SSA'=1, Omega'=Omega,Ext'=Ext*SSA'''
                    try:
                        result= np.multiply(self.optical_thickness_due_to_aerosol_sw,
                                            self.single_scattering_albedo_aerosol_sw)
                        self.optical_thickness_due_to_aerosol_sw= \
                                get_aerosol_waveband_data_array(result[0].values.T, units='dimensionless', numlevels=self.numlevels, sw=True)
                        self.single_scattering_albedo_aerosol_sw = \
                                get_aerosol_waveband_data_array(1, units='dimensionless', numlevels=self.numlevels, sw=True)
                       
                        if not self.includeScattering:
                            raise ValueError('For aerosols scattering and absorption can not both be deactivated')
                    except (ValueError):
                        exit('Please choose valid input data.')
                    

    def calculateHeightLevels(self, atmosphere):
        '''Used to translate the aerosol forcing data given as a function of height 
        to aerosol forcing data as a function of pressure levels
        '''
        heights = ty.pressure2height(atmosphere['plev'], atmosphere['T'][0, :])/1000
        return heights

class BackgroundAerosolStrato(Aerosol):
    '''
    stratospheric aerosol background
    '''
    def __init__(self,atmNumlevels,monthsAfterEruption=8,includeSWForcing=True,\
                 includeLWForcing=True):
        super().__init__(atmNumlevels,aerosol_type='all_aerosol_properties')
        self.numlevels=atmNumlevels
        self.includeSWForcing=includeSWForcing
        self.includeLWForcing=includeLWForcing
        self.monthsAfterEruption=monthsAfterEruption

    def update_aerosols(self, time, atmosphere):
        '''
        Import the stratospheric aerosol background data in first time step, taking into account
        the parameter settings of the VolcanoAerosol class.
        Translate from height dependance to pressure dependance.
        The aerosol layer is kept fixed and constant throughout the following run.
        '''
        if not np.count_nonzero(self.optical_thickness_due_to_aerosol_sw.values):
            if self.includeLWForcing:
                extEarth = xr.open_dataset(
                        os.path.join(
                                os.path.dirname(__file__),
                                'data/aerosolData/eva/23data0extEarthOrder.nc'
                                ))
            if self.includeSWForcing:
                extSun = xr.open_dataset(
                        os.path.join(
                                os.path.dirname(__file__),
                                'data/aerosolData/eva/23data0extSunOrder.nc'
                                ))
                gSun = xr.open_dataset(
                        os.path.join(
                                os.path.dirname(__file__),
                                'data/aerosolData/eva/23data0gSunOrder.nc'
                                ))
                omegaSun = xr.open_dataset(
                        os.path.join(
                                os.path.dirname(__file__),
                                'data/aerosolData/eva/23data0omegaSunOrder.nc'
                                ))
            heights = self.calculateHeightLevels(atmosphere)
            #the input data has to be scaled to fit to model levels
            #for compatability with rrtmg input format
            scaling=np.gradient(heights)
            
            if self.includeLWForcing:
                for lw_band in range(np.shape(extEarth.terrestrial_bands)[0]):
                    self.optical_thickness_due_to_aerosol_lw[lw_band, :] = \
                        sc.interpolate.interp1d(
                            extEarth.altitude.values,
                            extEarth.ext_earth[self.monthsAfterEruption,lw_band, :].values,
                            #extEarth.ext_earth[lw_band, :, 1].values,
                            bounds_error=False,
                            fill_value=0)(heights)*scaling
                        
            if self.includeSWForcing:
                for sw_band in range(np.shape(extSun.solar_bands)[0]):
                    self.optical_thickness_due_to_aerosol_sw[sw_band, :] = \
                        sc.interpolate.interp1d(
                            extSun.altitude.values,
                            extSun.ext_sun[sw_band,self.monthsAfterEruption, :].values,
                            #extSun.ext_sun[sw_band, :, 1],
                            bounds_error=False,
                            fill_value=0)(heights)*scaling
                    self.asymmetry_factor_aerosol_sw[sw_band, :] = \
                        sc.interpolate.interp1d(
                            gSun.altitude.values,
                            gSun.g_sun[sw_band,self.monthsAfterEruption, :].values,
                            #gSun.g_sun[sw_band, :, 1].values,
                            bounds_error=False,
                            fill_value=0)(heights)
                    self.single_scattering_albedo_aerosol_sw[sw_band, :] = \
                        sc.interpolate.interp1d(
                            omegaSun.altitude.values,
                            omegaSun.omega_sun[sw_band,self.monthsAfterEruption, :].values,
                            #omegaSun.omega_sun[sw_band, :, 1].values,
                            bounds_error=False,
                            fill_value=0)(heights)
                    

    def calculateHeightLevels(self, atmosphere):
        '''Used to translate the aerosol forcing data given as a function of height 
        to aerosol forcing data as a function of pressure levels
        '''
        heights = ty.pressure2height(atmosphere['plev'], atmosphere['T'][0, :])/1000
        return heights


class NoAerosol(Aerosol):
    '''
    No volcanic aerosol
    '''
    def __init__(self,atmNumlevels):
        super().__init__(atmNumlevels,aerosol_type='no_aerosol')
        
    def update_aerosols(self, time, atmosphere):
        return
    
    def calculateHeightLevels(self,atmosphere):
        return

# -*- coding: utf-8 -*-
"""Module containing classes describing different radiation models.
"""
import abc

from xarray import DataArray, Dataset
import numpy as np

from . import utils


__all__ = [
    'Radiation',
    'PSRAD',
]


class Radiation(metaclass=abc.ABCMeta):
    """Abstract base class to define requirements for radiation models."""
    def __init__(self, atmosphere, surface, zenith_angle=42.):
        """Return a radiation model.

        Parameters:
            zenith (float): Zenith angle of the sun.
        """
        self.atmosphere = atmosphere
        self.surface = surface
        self.zenith_angle = zenith_angle

    @abc.abstractmethod
    def get_heatingrates(self):
        """Returns the shortwave, longwave and net heatingrates."""
        pass


class PSRAD(Radiation):
    """Radiation model using the ICON PSRAD radiation scheme."""
    def _extract_psrad_args(self, atmosphere):
        """Returns tuple of mixing ratios to use with psrad.

        Paramteres:
            atmosphere (dict or pandas.DataFrame): Atmospheric atmosphere.

        Returns:
            tuple(ndarray): ndarrays in the order and unit to use with `psrad`:
                Z, P, T, x_vmr, ...
        """
        z = atmosphere['z'].values
        p = atmosphere['plev'].values / 100
        T = atmosphere['T'].values

        ret = [z, p, T]  # Z, P, T

        # Keep order as it is expected by PSRAD.
        required_gases = ['H2O', 'O3', 'CO2', 'N2O', 'CO', 'CH4']

        for gas in required_gases:
            if gas in atmosphere:
                ret.append(atmosphere[gas].values * 1e6)  # Append gas in ppm.
            else:
                ret.append(np.zeros(p.size))

        return tuple(ret)

    @utils.with_psrad_symlinks
    def get_heatingrates(self, atmosphere, surface):
        """Returns the shortwave, longwave and net heatingrates.

        Parameters:
            atmosphere (conrad.atmosphere.Atmosphere): Atmosphere model
                inherited from abstract class `conrad.atmosphere.Atmosphere`.
            surface (conrad.surface.Surface): Surface model inherited from
                abstract class `conrad.surface.Surface`.
        Returns:
            xarray.Dataset: Dataset containing for the simulated heating rates.
                The keys are 'sw_htngrt', 'lw_htngrt' and 'net_htngrt'.
        """
        from . import psrad
        self.psrad = psrad

        dmy_indices = np.asarray([0, 0, 0, 0])
        ic = dmy_indices.astype("int32") + 1
        c_lwc = np.asarray([0., 0., 0., 0.])
        c_iwc = np.asarray([0., 0., 0., 0.])
        c_frc = np.asarray([0., 0., 0., 0.])

        nlev = atmosphere['plev'].size

        # Extract surface properties.
        P_sfc = surface.pressure / 100
        T_sfc = surface.temperature
        albedo = surface.albedo
        zenith = self.zenith_angle

        self.psrad.setup_single(nlev, len(ic), ic, c_lwc, c_iwc, c_frc, zenith,
                                albedo, P_sfc, T_sfc,
                                *self._extract_psrad_args(atmosphere))

        ret = Dataset()  # Create xarray.Dataset for return values.

        # Shortwave heating rate.
        self.psrad.advance_lrtm()  # Perform PSRAD simulation.
        hr = self.psrad.get_lw_fluxes()[0]  # Ignore additional output.
        ret['lw_htngrt'] = DataArray(hr.ravel(),
                                     coords=[atmosphere['plev']],
                                     dims=['plev'])

        # Longwave heating rate.
        self.psrad.advance_srtm()
        hr = self.psrad.get_sw_fluxes()[0]
        ret['sw_htngrt'] = DataArray(hr.ravel(),
                                     coords=[atmosphere['plev']],
                                     dims=['plev'])

        # Net heating rate.
        ret['net_htngrt'] = ret['sw_htngrt'] + ret['lw_htngrt']

        return ret

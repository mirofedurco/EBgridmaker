import numpy as np
from copy import copy
from elisa import const as c, BinarySystem
from elisa.binary_system.model import (
    potential_value_primary,
    potential_value_secondary,
    pre_calculate_for_potential_value_primary,
    pre_calculate_for_potential_value_secondary
)
from elisa.binary_system.radius import calculate_side_radius
from .. utils.default_binary_model import DEFAULT_SYSTEM
from .. import config


def back_radius_potential_primary(radius, mass_ratio, synchronicity=1.0, distance=1.0):
    """
    Returns potential for given side radius.

    :param distance: float;
    :param synchronicity: float;
    :param radius: float;
    :param mass_ratio: float;
    :return: float;
    """
    # (F, q, d, phi, theta)
    args = (synchronicity, mass_ratio, distance, c.PI, c.HALF_PI)
    pot_args = pre_calculate_for_potential_value_primary(*args, return_as_tuple=True)
    return potential_value_primary(radius, mass_ratio, *pot_args)


def back_radius_potential_secondary(radius, mass_ratio, synchronicity=1.0, distance=1.0):
    """
    Returns potential for given side radius.

    :param radius: float; side radius of the secondary component
    :param mass_ratio: float;
    :return: float;
    """
    # (F, q, d, phi, theta)
    args = (synchronicity, mass_ratio, distance, c.PI, c.HALF_PI)
    pot_args = pre_calculate_for_potential_value_secondary(*args, return_as_tuple=True)
    return potential_value_secondary(radius, mass_ratio, *pot_args)


def secondary_side_radius(mass_ratio, surface_potential):
    """
    Side radius of secondary component
    :param mass_ratio: float;
    :param surface_potential: float;
    :return: float; side radius
    """
    return calculate_side_radius(1.0, mass_ratio, 1.0, surface_potential, 'secondary')


def critical_inclination(r1, r2, distance=None):
    """
    Returns minimum inclination for occurence of eclipses.

    :param r1: float;
    :param r2: float;
    :param distance: float;
    :return: Union[float; numpy.array]
    """
    summ = r1+r2
    if np.isscalar(summ):
        distance = 1.0 if distance is None else float(distance)
        return np.degrees(np.arccos((r1+r2)/distance))
    else:
        distance = np.full(summ.shape, 1.0) if distance is None else \
            (np.full(summ.shape, distance) if np.isscalar(distance) else distance)
        result = np.full(summ.shape, np.nan)
        summ = summ / distance
        mask = summ < 1
        result[mask] = np.degrees(np.arccos(summ[mask]/distance[mask]))
        return result


def correct_sma(mass_ratio, r1, r2):
    """
    Function will provide a values for sma and period that will create binary models with surface g within table
    coverage.

    :param mass_ratio: float;
    :param r1: float;
    :param r2: float;
    :return: tuple; sma in sol rad, period in days
    """
    mid_g = 270
    m1 = 4e30
    m2 = mass_ratio * m1

    sma1 = np.sqrt(c.G * m1 / (r1**2 * mid_g))
    sma2 = np.sqrt(c.G * m2 / (r2**2 * mid_g))

    sma = 0.5 * (sma1 + sma2)
    period = np.sqrt(c.FULL_ARC**2 * sma**3 / (c.G * (m1 + m2)))

    return 1.4374e-9 * sma, period / 86400


def initialize_system(mass_ratio, r1, r2, t1, t2, inclination, omega1, omega2, overcontact):
    """
    Initializing binary system based on grid params.

    :param mass_ratio: float;
    :param r1: float;
    :param r2: float;
    :param t1: int;
    :param t2: int;
    :param inclination: float;
    :param omega1: float;
    :param omega2: float;
    :param overcontact: bool;
    :return: elisa.BinarySystem
    """
    dt = t1 - t2
    if overcontact and np.abs(dt) > config.MAX_DIFF_T_OVERCONTACT:
        t2 = t1 - config.MAX_DIFF_T_OVERCONTACT if dt > 0.0 else t1 + config.MAX_DIFF_T_OVERCONTACT

    sma, period = correct_sma(mass_ratio, r1, r2)
    params = copy(DEFAULT_SYSTEM)
    params["system"].update({
        'inclination': inclination, 'mass_ratio': mass_ratio,
        'semi_major_axis': sma, 'period': period,
    })
    params["primary"].update({
        'surface_potential': omega1, 't_eff': t1
    })
    params["secondary"].update({
        'surface_potential': omega2, 't_eff': t2
    })

    return BinarySystem.from_json(params)


def invert_potential(potential, mass_ratio):
    return potential / mass_ratio + 0.5 * (mass_ratio - 1) / mass_ratio


def switch_components(mass_ratio, r1, r2, t1, t2, inclination, omega1, omega2):
    def inversion():
        new_omega_1 = invert_potential(omega2, mass_ratio)
        new_omega_2 = invert_potential(omega1, mass_ratio)

        return [1.0 / mass_ratio, r2, r1, t2, t1, inclination], new_omega_1, new_omega_2

    if t2 < t1:
        return [mass_ratio, r1, r2, t1, t2, inclination], omega1, omega2

    return inversion()


def return_closest_distance(binary):
    """
    Returns the closest component distance during eclipses.

    :param binary: BinarySystem;
    :return: float; distance in SMA units
    """
    conjunctions = binary.orbit.conjunctions
    conj_phases = [conj['true_phase'] for conj in conjunctions.values()]
    distances = binary.calculate_orbital_motion(conj_phases, return_nparray=True, calculate_from='phase')[:, 1]

    return distances.min()

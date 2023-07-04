import numpy as np
import scipy.special
import scipy.optimize
from SQDMetal.Utilities.QUtilities import QUtilities

class CpwParams:
    def __init__(self, rel_permittivity, dielectric_thickness):
        self.rel_permittivity = rel_permittivity
        self.dielectric_thickness = dielectric_thickness
    
    @classmethod
    def fromQDesign(cls, design, chip_name='main'):
        matr = design.chips[chip_name].material
        if matr == 'silicon':
            er = 11.45 # room temp silicon (11.7) vs ultra-cold silicon (11.45)
        else:
            assert False, "Unrecognised material - cannot infer permittivity."
        h = QUtilities.parse_value_length(design.chips[chip_name].size['size_z'])
        return CpwParams(er, h)

    @staticmethod
    def calc_impedance(tr_wid, tr_gap, er, h):
        a = tr_wid
        b = tr_wid + 2.0*tr_gap
        k = a/b
        k1 = np.tanh(np.pi*a/(4.0*h)) / np.tanh(np.pi*b/(4.0*h))
        kp = np.sqrt(1-k**2)
        k1p = np.sqrt(1-k1**2)

        kp_k1_on_k_k1p = scipy.special.ellipk(kp**2)*scipy.special.ellipk(k1**2) / (scipy.special.ellipk(k**2)*scipy.special.ellipk(k1p**2))
        e_eff = (1.0 + er*kp_k1_on_k_k1p)/(1.0 + kp_k1_on_k_k1p)

        z0 = 60.0*np.pi/np.sqrt(e_eff) * 1.0 / (scipy.special.ellipk(k**2)/scipy.special.ellipk(kp**2) + scipy.special.ellipk(k1**2)/scipy.special.ellipk(k1p**2))

        return z0

    def get_gap_from_width(self, trace_width, target_impedance=50):
        er = self.rel_permittivity
        h = self.dielectric_thickness

        def func(gap, wid, er, h):
            return CpwParams.calc_impedance(wid, )

        x0 = [trace_width]

        res = scipy.optimize.minimize(lambda x: np.abs(CpwParams.calc_impedance(trace_width, x[0], er, h)-target_impedance), x0, method='Nelder-Mead', tol=1e-6)

        return res.x[0]



import qiskit_metal as metal
from qiskit_metal import designs, draw
from qiskit_metal import MetalGUI, Dict, Headings
from qiskit_metal.qlibrary.terminations.open_to_ground import OpenToGround
from qiskit_metal.qlibrary.tlines.meandered import RouteMeander
from qiskit_metal.qlibrary.qubits.transmon_pocket import TransmonPocket

from SQDMetal.Utilities.MakeGDS import MakeGDS

import shutil
import unittest

class TestGDS(unittest.TestCase):
    ERR_TOL = 5e-13
    
    def initialise(self):
        self._folder_path = 'TestDesign'

    def cleanup(self):
        shutil.rmtree(self._folder_path)

    def test_GDSexport(self):
        self.initialise()

        design = designs.DesignPlanar({}, True)
        design.chips.main.size.center_x = '0.5mm'
        design.chips.main.size.center_y = '0.1mm'
        design.chips.main.size['size_x'] = '2.8mm'
        design.chips.main.size['size_y'] = '2mm'

        q1 = TransmonPocket(design, 'Q1', options = dict(
            pad_width = '425 um',
            pocket_height = '650um',
            connection_pads=dict(
                readout = dict(loc_W=+1,loc_H=+1, pad_width='200um')
            )))

        otg = OpenToGround(design, 'open_to_ground', options=dict(pos_x='1.75mm',  pos_y='0um', orientation='0'))
        RouteMeander(design, 'readout',  Dict(
                total_length='6 mm',
                hfss_wire_bonds = True,
                fillet='90 um',
                lead = dict(start_straight='100um'),
                pin_inputs=Dict(
                start_pin=Dict(component='Q1', pin='readout'),
                end_pin=Dict(component='open_to_ground', pin='open')), ))

        # GDS export
        design.rebuild()
        export_name = "unit_test.gds"
        gds_out = MakeGDS(design)
        gds_out.export(export_name, export_type="positive")
        gds_out.export(export_name, export_type="negative")
        gds_out.export(export_name, export_type="all")
        gds_out.export(export_name, export_layers=[0, 1])
        gds_out.export(export_name)

        self.cleanup()

if __name__ == '__main__':
    TestGDS().test_GDSexport()
    unittest.main()
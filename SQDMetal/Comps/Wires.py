# -*- coding: utf-8 -*-

# Copyright 2025 Prasanna Pakkiam
# SPDX-License-Identifier: Apache-2.0
# Author: Prasanna Pakkiam
# Creation Date: 01/05/2023
# Description: Collection of classes to wires - from routing objects to tapers.

from qiskit_metal.qlibrary.core import QComponent, QRoute
from qiskit_metal import draw
import numpy as np
import shapely
from qiskit_metal.toolbox_python.attr_dict import Dict
from SQDMetal.Utilities.QUtilities import QUtilities

class WirePinStretch(QRoute):
    """Creates a wire that extends some distance away from some target component's pin. It also has provisions to provide
    gaps in the start and/or end to the ground plane (e.g. for open-ended terminations).

    Inherits QComponent class.

    The positioning can be done dynamically via:
        * pin_inputs=Dict(start_pin=Dict(component=f'...',pin='...')) - Specifying start position via a component pin
        * dist_extend - Distance upon to stretch away from the start pin.
    The resulting wire is a straight section with width equal to that specified by the start pin and extends dist_extend
    from the start pin (in the direction given by the start pin).

    The part additionally has options to add ground cuts to the start and end portions (e.g. open-ended terminations):
        * start_gap - Distance to cut into ground plane at start.
        * end_gap   - Distance to cut into ground plane at end.
    The values are interpreted as follows:
        - start_gap, end_gap > 0, the gap to the ground plane is the supplied value
        - start_gap, end_gap == 0, the gap to the ground plane is taken as trace_gap
        - start_gap, end_gap < 0, no gap is given.        

    As usual trace_width and trace_gap specify the CPW dimensions.

    Pins:
        There are three pins in the end section:
            * end
            * end_L
            * end_R
        where end is flush in the direction of the wire, while end_L and end_R are on the sides:
        
                        <-w->             x = start pin location 
         _________________l__             e = 'end' pin
        |                    |  /|\       l = 'end_L' pin
        x                    e   w        r = 'end_R' pin
        |_________________r__|  \|/       d = dist_extend
        <----------d--------->            w = width of start pin

    .. image::
        Cap3Interdigital.png

    .. meta::
        Wire that extends off a pin.

    Default Options:
        * dist_extend='10um'
        * start_gap='-1um'
        * end_gap='-1um'
    """

    default_options = Dict(dist_extend='10um',
                           start_gap='-1um',
                           end_gap='-1um')

    def __init__(self, design,
                        name: str = None,
                        options: Dict = None,
                        type: str = "CPW",
                        **kwargs):
        #QRoute forces an end-pin to exist... So make it artificial...
        options.pin_inputs['end_pin'] = Dict(component=options.pin_inputs.start_pin.component, pin=options.pin_inputs.start_pin.pin)
        options.fillet='0um'
        super().__init__(design, name, options, **kwargs)

    def make(self):
        p = self.p

        self.set_pin("start")
        
        start_point = self.design.components[self.options.pin_inputs.start_pin.component].pins[self.options.pin_inputs.start_pin.pin]
        startPt = start_point['middle']
        norm = start_point['normal']
        endPt = startPt + norm*p.dist_extend

        self.add_pin('end', [endPt-norm, endPt], width=p.trace_width, input_as_norm=True)
        tang = np.array([-norm[1],norm[0]])
        pt = endPt+tang*p.trace_width*0.5-norm*p.trace_width*0.5
        self.add_pin('endL', [pt-tang, pt], width=p.trace_width, input_as_norm=True)
        pt = endPt-tang*p.trace_width*0.5-norm*p.trace_width*0.5
        self.add_pin('endR', [pt+tang, pt], width=p.trace_width, input_as_norm=True)
        
        line = shapely.LineString(np.array([startPt, endPt]))
        line_gap = np.array([startPt, endPt])
        if p.start_gap > 0:
            line_gap[0] -= norm*p.start_gap
        elif p.start_gap == 0:
            line_gap[0] -= norm*p.trace_gap
        if p.end_gap > 0:
            line_gap[1] += norm*p.end_gap
        elif p.end_gap == 0:
            line_gap[1] += norm*p.trace_gap
        line_gap = shapely.LineString(line_gap)

        self.add_qgeometry('path', {'trace': line},
                           width=p.trace_width,
                           fillet=p.fillet,
                           layer=p.layer)
        self.add_qgeometry('path', {'cut': line_gap},
                               width=p.trace_width + 2 * p.trace_gap,
                               fillet=p.fillet,
                               layer=p.layer,
                               subtract=True)
        # self.make_elements(np.array([startPt, endPt]))

class WirePins(QRoute):
    """Rudimentary manual routing wire that passes through all the listed pins. It supports CPW cutouts and an additional
    gap in the end for open-ended terminations.

    Inherits QComponent class.

    The CPW wire parameters are given via:
        * trace_width - width of CPW
        * trace_gap - gap to ground plane around CPW
        * fillet    - radius of fillet/turns on every corner
        * end_gap   - gap to ground plane at the end of the wire (useful for open-ended terminations)

    The waypoints for the positioning/routing is given via a list of pins in 'pathObjPins'. Each pin can be either:
        * 2-tuple signifying the component name and the pin name
        * Single string - in this case, it is presumed that the pin name is 'a' (as is the case with most Joints)
    For example:
        pathObjPins=[('Launcher1', 'tie'), 'jnt_1', 'jnt_2', ('Launcher2', 'tie')]

    Pins:
        There are no inherent pins in this object, but they can be added manually via constructs like RouteJoint

    .. image::
        Cap3Interdigital.png

    .. meta::
        Wire that hits manually selected pins.

    Default Options:
        * pathObjPins=[]    <--- Needs to have at least 2 pins to form a path!
        * trace_width='10um'
        * trace_gap='10um'
        * fillet='50um'
        * end_gap='0um'
    """

    default_options = Dict(pathObjPins=[],
                           trace_width='10um', trace_gap='10um', fillet='50um', end_gap='0um',
                           advanced=Dict(avoid_collision='false'))
    
    def __init__(self, design,
                        name: str = None,
                        options: Dict = None,
                        type: str = "CPW",
                        **kwargs):
        #QRoute forces an end-pin to exist... So make it artificial...
        pins = []
        for cur_pin in [options.pathObjPins[0], options.pathObjPins[-1]]:
            if isinstance(cur_pin, list) or isinstance(cur_pin, tuple):
                comp, pin = cur_pin[0], cur_pin[1]
            else:
                comp, pin = cur_pin, 'a'
            pins += [(comp, pin)]
        assert len(pins) > 0, "Must have at least 2 pins/waypoints."
        options.pin_inputs['start_pin'] = Dict(component=pins[0][0], pin=pins[0][1])
        options.pin_inputs['end_pin'] = Dict(component=pins[1][0], pin=pins[1][1])
        super().__init__(design, name, options, **kwargs)

    def make(self):
        p = self.p

        #Parse Path Joints...
        pins = []
        for cur_pin in self.options.pathObjPins:
            if isinstance(cur_pin, list) or isinstance(cur_pin, tuple):
                comp, pin = cur_pin[0], cur_pin[1]
            else:
                comp, pin = cur_pin, 'a'
            pins += [self.design.components[comp].pins[pin]['middle']]

        line = shapely.LineString(np.vstack(pins))
        if p.end_gap > 0:
            norm_vec = pins[-1]-pins[-2]
            norm_vec = norm_vec / np.linalg.norm(norm_vec) * p.end_gap
            pins[-1] = pins[-1] + norm_vec
            line_gap = shapely.LineString(np.vstack(pins))
        else:
            line_gap = line

        self.set_pin("start")
        self.set_pin("end")
        self.add_qgeometry('path', {'trace': line},
                           width=p.trace_width,
                           fillet=p.fillet,
                           layer=p.layer)
        self.add_qgeometry('path', {'cut': line_gap},
                               width=p.trace_width + 2 * p.trace_gap,
                               fillet=p.fillet,
                               layer=p.layer,
                               subtract=True)

class WireElbowParallelPinPin(QRoute):
    """A rudimentary wire connector that mimics the 'Microsoft Office Autoshapes Elbow Connector with yellow handle' with curved corners.
    The connecting pins must be either parallel or anti-parallel

    Inherits QRoute class.

    Wire Metal Geometry and Ground Cutout Pocket:
        * frac_pos_elbow - Position of the crossward part of the elbow; only exists when the pins are anti-parallel. It is a fraction where
                           0.0 is next to the start pin while 1.0 is next to the end pin.
        * fillet - Radius of the turns on the elbows
        * pin_pad - Minimum distance to traverse before turning from a given pin (making it non-zero helps ensure it passes the 'bad-fillet'
                    checks in Qiskit-Metal). Ignored in the 2 Elbows, anti-parallel case shown below...
        * end_gap   - gap to ground plane at the end of the wire (useful for open-ended terminations)
    The parameters trace_width and trace_gap define the CPW dimensions.

    The positioning can be done dynamically via:
        * pin_inputs=Dict(start_pin=Dict(component='...',pin='...'), end_pin=Dict(component='...',pin='...')) - Specifying start and end
          positions via a component pins

    Sketch:
        Below is a sketch of the wiring configurations available depending on the position of the pins
        ::
                       P  R                   f                             P  R            R = fillet
                   p1>----\            p1>----\ R                       p1>----\            P = pin_pad
                          |                   |                                |            f = frac_pos_elbow
                          |                   |                   /------------/ f
                          |                   |                   |
                 p2>------/                   \---<p2             \---<p2
            Parallel, 2 Elbows     Anti-parallel, 2 Elbows     Anti-parallel, 4 Elbows

        Notice that frac_pos_elbow is only relevant in the anti-parallel pin configurations. In the 2-elbow case, it controls the position of
        the long vertical edge in the direction of the pins, while in the 4-elbow cases, it controls the direction of the long horizontal edge
        in the direction perpendicular to the pins.

    .. image::
        Cap3Interdigital.png

    .. meta::
        Wire with Elbow between colinear pins

    Default Options:
        * frac_pos_elbow=0.5
        * fillet='20um'
        * pin_pad='2um'
        * end_gap='0um'
    """

    default_options = Dict(frac_pos_elbow=0.5, fillet='20um', pin_pad='2um', end_gap='0um')

    def make(self):
        p = self.p

        start_point = self.design.components[self.options.pin_inputs.start_pin.component].pins[self.options.pin_inputs.start_pin.pin]
        startPt = start_point['middle']
        start_norm = start_point['normal']

        end_point = self.design.components[self.options.pin_inputs.end_pin.component].pins[self.options.pin_inputs.end_pin.pin]
        endPt = end_point['middle']
        end_norm = end_point['normal']

        assert np.abs(start_norm[0]*end_norm[1] - start_norm[1]*end_norm[0]) < 1e-15, "The two pins must be facing either parallel or anti-parallel."

        matRot = np.array([[start_norm[0], start_norm[1]], [-start_norm[1], start_norm[0]]])
        start_norm = matRot @ start_norm
        end_norm = matRot @ end_norm
        endPt = matRot @ (endPt-startPt)

        if end_norm[0] > 0:
            #2 Elbows - parallel
            if endPt[0] > 0:
                path = [[0,0], [endPt[0]+p.pin_pad+p.fillet, 0], [endPt[0]+p.pin_pad+p.fillet, endPt[1]], endPt]
            else:
                path = [[0,0], [p.pin_pad+p.fillet,0], [p.pin_pad+p.fillet, endPt[1]], endPt]
        elif endPt[0] >= 2*(p.pin_pad + p.fillet):
            #2 Elbows - anti-parallel
            path = [[0,0], [endPt[0]*p.frac_pos_elbow, 0], [endPt[0]*p.frac_pos_elbow, endPt[1]], endPt]
        else:
            #4 Elbows - anti-parallel            
            path = [[0,0], [p.pin_pad+p.fillet, 0],
                    [p.pin_pad+p.fillet, endPt[1]*p.frac_pos_elbow], [endPt[0]-p.pin_pad-p.fillet, endPt[1]*p.frac_pos_elbow],
                    [endPt[0]-p.pin_pad-p.fillet, endPt[1]], endPt]
        
        path = matRot.T @ np.array(path).T
        path = path.T
        path[:,0] += startPt[0]
        path[:,1] += startPt[1]

        line = shapely.LineString(np.vstack(path))
        if p.end_gap > 0:
            norm_vec = path[-1]-path[-2]
            norm_vec = norm_vec / np.linalg.norm(norm_vec) * p.end_gap
            path[-1] = path[-1] + norm_vec
            line_gap = shapely.LineString(np.vstack(path))
        else:
            line_gap = line

        self.set_pin("start")
        self.set_pin("end")
        self.add_qgeometry('path', {'trace': line},
                           width=p.trace_width,
                           fillet=p.fillet,
                           layer=p.layer)
        self.add_qgeometry('path', {'cut': line_gap},
                               width=p.trace_width + 2 * p.trace_gap,
                               fillet=p.fillet,
                               layer=p.layer,
                               subtract=True)


class WireElbowSingle(QRoute):
    """A wire connection that has one corner/elbow turn to connect two pins.

    Inherits QRoute class.

    Wire Metal Geometry and Ground Cutout Pocket:
        * fillet - Radius of the turns on the elbows
    The parameters trace_width and trace_gap define the CPW dimensions.

    The positioning can be done dynamically via:
        * pin_inputs=Dict(start_pin=Dict(component=f'...',pin='...'), end_pin=Dict(component=f'...',pin='...')) - Specifying start and end
          positions via a component pins

    Sketch:
        Below is a sketch of the wiring configurations available depending on the position of the pins
        ::
            P1###########
                         #
                          #             # = Wire
                           #            P1 and P2 = the pins between which the wire connects
                            #
                             P2

        Notice that the pin directions point in direction of wire segments. The turning corner is set at the line intersection of the two pin
        vectors. Thus, this shouldn't be used when the pins are facing away from one another.

    .. image::
        Cap3Interdigital.png

    .. meta::
        Wire with single corner between pins

    Default Options:
        * trace_width='10um'
        * trace_gap='10um'
        * fillet='20um'
    """

    default_options = Dict(trace_width='10um',
                           trace_gap='10um',
                           fillet='20um')

    def make(self):
        p = self.p  # noqa: F841 # abhishekchak52: unused variable p

        start_point = self.design.components[self.options.pin_inputs.start_pin.component].pins[self.options.pin_inputs.start_pin.pin]
        startPt = start_point['middle']
        start_norm = start_point['normal']

        end_point = self.design.components[self.options.pin_inputs.end_pin.component].pins[self.options.pin_inputs.end_pin.pin]
        endPt = end_point['middle']
        end_norm = end_point['normal']
        
        try:
            t,u = np.linalg.solve([[start_norm[0], end_norm[0]], [start_norm[1], end_norm[1]]], [endPt[0]-startPt[0], endPt[1]-startPt[1]])
        except Exception:
            raise Exception("The pins are parallel and this construct should not be used. Try for example, WireElbowParallelPinPin or WirePins instead.")
        assert t > 0, "The pins are facing away and will cause the turn to occur at some point behind the components. Check direction of pins."
        midPt = startPt+start_norm*t

        path = [startPt, midPt, endPt]

        self.set_pin("start")
        self.set_pin("end")
        self.make_elements(path)

class WireTaperPinStretch(QComponent):
    """A taper to change width of wire at some pin.

    Inherits QComponent class.

    Wire Metal Geometry and Ground Cutout Pocket:
        * dist_extend - Length of taper
        * orig_gap    - If the target pin is a CPW, this argument will be ignored and the trace_gap parameter from the pin's CPW component
                        will be taken. Otherwise, the initial CPW gap will be taken from orig_gap.
    The parameters trace_width and trace_gap define the final CPW dimensions.

    The positioning can be done dynamically via:
        * pin_inputs=Dict(start_pin=Dict(component=f'...',pin='...')) - Specifying start and end
          positions via a component pins

    Pins:
        There is a pin called 'a' to continue the taper onto a wire of different width.

    Sketch:
        Below is a sketch of the wiring configurations available depending on the position of the pins
        ::
              @@@@@@G
              @@@@  G           # = Taper
              @@    G           @ = Ground plane
             g    ## /|\        P = Pin to attach taper
             g  ####  |         W = trace_width
              ######  |         G = trace_gap
            P ######  W         D = dist_extend
              ######  |         g = orig_gap
                ####  |
                  ## \|/
              <..D.>
              @@@@
              @@@@@@

        Notice that the pin directions point in direction of wire segments. The turning corner is set at the line intersection of the two pin
        vectors. Thus, this shouldn't be used when the pins are facing away from one another.

    .. image::
        Cap3Interdigital.png

    .. meta::
        Taper to change width of wire at some pin.

    Default Options:
        * trace_width='20um'
        * trace_gap='10um'
        * dist_extend='30um'
        * orig_gap='10um'
    """
    default_options = Dict(trace_width='20um',
                           trace_gap='10um',
                           dist_extend='30um',
                           orig_gap='10um')

    def __init__(self, design,
                    name: str = None,
                    options: Dict = None,
                    type: str = "CPW",
                    **kwargs):
        #QRoute forces an end-pin to exist... So make it artificial...
        assert 'pin_inputs' in options, "Must provide a starting pin input via \'pin_inputs\'."
        assert 'start_pin' in options.pin_inputs, "Must provide \'start_pin\' in \'pin_inputs\'."
        assert 'component' in options.pin_inputs.start_pin, "Must provide \'component\' in \'start_pin\'."
        assert 'pin' in options.pin_inputs.start_pin, "Must provide \'pin\' in \'start_pin\'."
        super().__init__(design, name, options, **kwargs)
        #TODO: Perhaps a pull request to add poppable options?

    def make(self):
        """This is executed by the user to generate the qgeometry for the
        component."""
        p = self.p
        #########################################################

        start_point = self.design.components[self.options.pin_inputs.start_pin.component].pins[self.options.pin_inputs.start_pin.pin]
        startPt = start_point['middle']
        norm = start_point['normal']
        rot_angle = np.arctan2(norm[1], norm[0])
        width = start_point['width']
        if 'trace_gap' in self.design.components[self.options.pin_inputs.start_pin.component].options:
            gap = self.design.components[self.options.pin_inputs.start_pin.component].options['trace_gap']
            #In case it is using a parameter - e.g. cpw_width or cpw_gap...
            if isinstance(gap, str):
                if gap in self.design.variables:
                    gap = QUtilities.parse_value_length(self.design.variables[gap])
                gap = QUtilities.parse_value_length(gap) / QUtilities.get_units(self.design)
        else:
            gap = p.orig_gap

        taper = [
                (0, width*0.5),
                (p.dist_extend, p.trace_width*0.5),
                (p.dist_extend, -p.trace_width*0.5),
                (0, -width*0.5)]

        taper_gap = [
                    (0, width*0.5+gap),
                    (p.dist_extend, p.trace_width*0.5+p.trace_gap),
                    (p.dist_extend, -p.trace_width*0.5-p.trace_gap),
                    (0, -width*0.5-gap)]

        pin = shapely.LineString(taper[1:3])
        taper = shapely.Polygon(taper)
        taper_gap = shapely.Polygon(taper_gap)

        polys = [taper, taper_gap, pin]
        polys = draw.rotate(polys, rot_angle, origin=(0, 0), use_radians=True)
        polys = draw.translate(polys, *startPt)
        [taper, taper_gap, pin] = polys
        
        # Adds the object to the qgeometry table
        self.add_qgeometry('poly',
                           dict(taper=taper),
                           layer=p.layer)

        #subtracts out ground plane on the layer it's on
        self.add_qgeometry('poly',
                           dict(taper_gap=taper_gap),
                           subtract=True,
                           layer=p.layer)

        # Generates its own pins
        self.add_pin('a', pin.coords, width=p.trace_width)

class WireTaperProbePinStretch(QComponent):
    """A taper that splits into two probes.

    Inherits QComponent class.

    Wire Metal Geometry and Ground Cutout Pocket:
        * dist_extend - Length of taper
        * orig_gap    - If the target pin is a CPW, this argument will be ignored and the trace_gap parameter from the pin's CPW component
                        will be taken. Otherwise, the initial CPW gap will be taken from orig_gap.
        * probe_gap1  - Gap between the two probes in the taper at origin
        * probe_gap2  - Gap between the two probes in the taper at the end of the extension
        * layer_probe2 - If greater than -1, it will place the second probe into this layer.
        
    The parameters trace_width and trace_gap define the final CPW dimensions.

    The positioning can be done dynamically via:
        * pin_inputs=Dict(start_pin=Dict(component=f'...',pin='...')) - Specifying start and end
          positions via a component pins

    Pins:
        There are pins called 'L' and 'R' on the ends of the two probes

    Sketch:
        Below is a sketch of the wiring configurations available depending on the position of the pins
        ::
              @@@@@@G
              @@@@  G           # = Taper
              @@    G           @ = Ground plane
             g     #  W         
             g    ##L W         P = Pin to attach taper
             g  ####  W         W = trace_width
         w    ###  2            G = trace_gap
         w    1    2            g = orig_gap
         w  P 1    2            D = dist_extend
         w    1    2            1 = probe_gap1
         w    ###  2            2 = probe_gap2
                ####  W         L = New pin to attach a probe wire
                  ##R W         R = New pin to attach a probe wire
                   #  W         w = The width parameter of pin P
              <..D.>
              @@@@
              @@@@@@

        Notice that the pin directions point in direction of wire segments. The turning corner is set at the line intersection of the two pin
        vectors. Thus, this shouldn't be used when the pins are facing away from one another.

    .. image::
        Cap3Interdigital.png

    .. meta::
        Taper to change width of wire at some pin.

    Default Options:
        * trace_width='20um'
        * trace_gap='10um'
        * dist_extend='30um'
        * orig_gap='10um'
        * probe_gap1='2um'
        * probe_gap2='4um'
        * layer_probe2=-1
    """
    default_options = Dict(trace_width='20um',
                           trace_gap='10um',
                           dist_extend='30um',
                           orig_gap='10um',
                           probe_gap1='2um',
                           probe_gap2='4um',
                           layer_probe2=-1)

    def __init__(self, design,
                    name: str = None,
                    options: Dict = None,
                    type: str = "CPW",
                    **kwargs):
        #QRoute forces an end-pin to exist... So make it artificial...
        assert 'pin_inputs' in options, "Must provide a starting pin input via \'pin_inputs\'."
        assert 'start_pin' in options.pin_inputs, "Must provide \'start_pin\' in \'pin_inputs\'."
        assert 'component' in options.pin_inputs.start_pin, "Must provide \'component\' in \'start_pin\'."
        assert 'pin' in options.pin_inputs.start_pin, "Must provide \'pin\' in \'start_pin\'."
        super().__init__(design, name, options, **kwargs)
        #TODO: Perhaps a pull request to add poppable options?

    def make(self):
        """This is executed by the user to generate the qgeometry for the
        component."""
        p = self.p
        #########################################################

        start_point = self.design.components[self.options.pin_inputs.start_pin.component].pins[self.options.pin_inputs.start_pin.pin]
        startPt = start_point['middle']
        norm = start_point['normal']
        rot_angle = np.arctan2(norm[1], norm[0])
        width = start_point['width']
        if 'trace_gap' in self.design.components[self.options.pin_inputs.start_pin.component].options:
            gap = self.design.components[self.options.pin_inputs.start_pin.component].options['trace_gap']
            #In case it is using a parameter - e.g. cpw_width or cpw_gap...
            if isinstance(gap, str):
                gap = QUtilities.parse_value_length(self.design.variables[gap])
                gap = QUtilities.parse_value_length(gap) / QUtilities.get_units(self.design)
        else:
            gap = p.orig_gap

        taper1 = [
                (0, width*0.5),
                (0, p.probe_gap1*0.5),
                (p.dist_extend, p.probe_gap2*0.5),
                (p.dist_extend, p.trace_width + p.probe_gap2*0.5)]
        taper2 = [
                (0, -p.probe_gap1*0.5),
                (0, -width*0.5),
                (p.dist_extend, -p.trace_width - p.probe_gap2*0.5),
                (p.dist_extend, -p.probe_gap2*0.5)]

        taper_gap = [
                    (0, width*0.5+gap),
                    (p.dist_extend, p.trace_width + p.probe_gap2*0.5+p.trace_gap),
                    (p.dist_extend, -p.trace_width - p.probe_gap2*0.5-p.trace_gap),
                    (0, -width*0.5-gap)]

        pinL = shapely.LineString(taper1[2:])
        pinR = shapely.LineString(taper2[2:])
        taper1 = shapely.Polygon(taper1)
        taper2 = shapely.Polygon(taper2)
        taper_gap = shapely.Polygon(taper_gap)

        polys = [taper1, taper2, taper_gap, pinL, pinR]
        polys = draw.rotate(polys, rot_angle, origin=(0, 0), use_radians=True)
        polys = draw.translate(polys, *startPt)
        [taper1, taper2, taper_gap, pinL, pinR] = polys
        
        # Adds the object to the qgeometry table
        self.add_qgeometry('poly',
                           dict(taper1=taper1),
                           layer=p.layer)

        if p.layer_probe2 < 0:
            p.layer_probe2 = p.layer
        self.add_qgeometry('poly',
                           dict(taper2=taper2),
                           layer=p.layer_probe2)

        #subtracts out ground plane on the layer it's on
        self.add_qgeometry('poly',
                           dict(taper_gap=taper_gap),
                           subtract=True,
                           layer=p.layer)

        # Generates its own pins
        self.add_pin('L', pinL.coords[::-1], width=p.trace_width)
        self.add_pin('R', pinR.coords[::-1], width=p.trace_width)

class HallBar(QComponent):
    """
    A Hall Bar component consisting of 8 probe pads for resistance measurements.

    Inherits QComponent class.

    Probe Pad geometry:
        * pad_width     - Width (x) of probe pads
        * pad_height    - Height (y) of probe pads
        * pocket_width  - Width (x) of ground plane cutout
        * pocket_height - Height (x) of ground plane cutout

    Hall Bar geometry:
        * trace_width   - Width of the main conductor
        * T_height      - Height of the T-bars (along y)
        * num_sq_short  - Number of squares along the conductor between the two inner probe pads
        * num_sq_long   - Number of squares along the conductor between the two outer probe pads

    Positioning:
        * pos_x         - X position
        * pos_y         - Y position
        * layer         - layer number
    
    Patches:
        * add_patches   - add patches to probe pads

    Pins:
        There are no pins.

    Sketch:
        Below is a sketch of the Hall bar

        Total width determined by num_sq_long (default 100).

        <-----NSL*TW----->          NSS : num_sq_short
         _   _      _   _           NSL : num_sq_short
        |_| |_|    |_| |_|     TH   TH  : T_height
        |     |    |     |     TH   TW  : trace_width       
        |_____|____|_____|     TH   PW  : pad_width   
        |     |    |     |     TH   PH  : pad_height  
        |_   _|    |_   _|     TH
        |_| |_|    |_| |_| PH  TH   y
               <-->     PW          |
               NSS                  --- x
        ::
            
    """
    default_options = Dict(pos_x="0mm",
                           pos_y="0mm",
                           trace_width='10um',
                           num_sq_short=10,
                           num_sq_long=100,
                           pad_width="150um",
                           pad_height="100um",
                           pocket_width="1.4mm",
                           pocket_height="1.0mm",
                           T_height="500um",
                           fillet_radius="20um",
                           layer=0,
                           patches=True,
                           patch_layer=3
                        )
    
    def __init__(self, design,
                    name: str = None,
                    options: Dict = None,
                    type: str = "CPW",
                    **kwargs):
        super().__init__(design, name, options, **kwargs)
    
    def make(self):
        """This is executed by the user to generate the qgeometry for the
        component."""
        p = self.p
        trace_short = p.num_sq_short * p.trace_width
        trace_long = p.num_sq_long * p.trace_width

        # draw
        main_trace = draw.rectangle(trace_long, p.trace_width)
        pocket = draw.rectangle(p.pocket_width, p.pocket_height)
        far_T_L = draw.rectangle(p.trace_width, p.T_height,  xoff=-0.5*trace_long)
        far_T_R = draw.rectangle(p.trace_width, p.T_height,  xoff=0.5*trace_long)
        near_T_L = draw.rectangle(p.trace_width, p.T_height, xoff=-0.5*trace_short)
        near_T_R = draw.rectangle(p.trace_width, p.T_height, xoff=0.5*trace_short)
        pad_U_L = draw.rectangle(p.pad_width, p.pad_height,  xoff=-0.5*trace_long+0.5*p.pad_width-0.5*p.trace_width,  yoff=0.5*p.T_height)
        pad_U_ML = draw.rectangle(p.pad_width, p.pad_height, xoff=-0.5*trace_short-0.5*p.pad_width+0.5*p.trace_width, yoff=0.5*p.T_height)
        pad_U_MR = draw.rectangle(p.pad_width, p.pad_height, xoff=0.5*trace_short+0.5*p.pad_width-0.5*p.trace_width,  yoff=0.5*p.T_height)
        pad_U_R = draw.rectangle(p.pad_width, p.pad_height,  xoff=0.5*trace_long-0.5*p.pad_width+0.5*p.trace_width,  yoff=0.5*p.T_height)
        pad_L_L = draw.rectangle(p.pad_width, p.pad_height,  xoff=-0.5*trace_long+0.5*p.pad_width-0.5*p.trace_width,  yoff=-0.5*p.T_height)
        pad_L_ML = draw.rectangle(p.pad_width, p.pad_height, xoff=-0.5*trace_short-0.5*p.pad_width+0.5*p.trace_width, yoff=-0.5*p.T_height)
        pad_L_MR = draw.rectangle(p.pad_width, p.pad_height, xoff=0.5*trace_short+0.5*p.pad_width-0.5*p.trace_width,  yoff=-0.5*p.T_height)
        pad_L_R = draw.rectangle(p.pad_width, p.pad_height,  xoff=0.5*trace_long-0.5*p.pad_width+0.5*p.trace_width,  yoff=-0.5*p.T_height)

        # merge 
        T_ends = shapely.ops.unary_union([far_T_L, far_T_R])
        T_mids = shapely.ops.unary_union([near_T_L, near_T_R])
        pads_L = shapely.ops.unary_union([pad_L_L, pad_L_ML, pad_L_MR, pad_L_R])
        pads_U = shapely.ops.unary_union([pad_U_L, pad_U_ML, pad_U_MR, pad_U_R])

        # merge all pads and T's
        pads_and_Ts = shapely.ops.unary_union([T_ends, T_mids, pads_L, pads_U])
        pads_and_Ts = pads_and_Ts.buffer(p.fillet_radius).buffer(-p.fillet_radius)
        pads_and_Ts = pads_and_Ts.buffer(-0.48*p.trace_width).buffer(0.48*p.trace_width)

        # patches
        if p.patches:
            patch_U_L = draw.rectangle(p.pad_width, p.pad_height,  xoff=-0.5*trace_long+0.5*p.pad_width-0.5*p.trace_width,  yoff=0.5*p.T_height)
            patch_U_ML = draw.rectangle(p.pad_width, p.pad_height, xoff=-0.5*trace_short-0.5*p.pad_width+0.5*p.trace_width, yoff=0.5*p.T_height)
            patch_U_MR = draw.rectangle(p.pad_width, p.pad_height, xoff=0.5*trace_short+0.5*p.pad_width-0.5*p.trace_width,  yoff=0.5*p.T_height)
            patch_U_R = draw.rectangle(p.pad_width, p.pad_height,  xoff=0.5*trace_long-0.5*p.pad_width+0.5*p.trace_width,  yoff=0.5*p.T_height)
            patch_L_L = draw.rectangle(p.pad_width, p.pad_height,  xoff=-0.5*trace_long+0.5*p.pad_width-0.5*p.trace_width,  yoff=-0.5*p.T_height)
            patch_L_ML = draw.rectangle(p.pad_width, p.pad_height, xoff=-0.5*trace_short-0.5*p.pad_width+0.5*p.trace_width, yoff=-0.5*p.T_height)
            patch_L_MR = draw.rectangle(p.pad_width, p.pad_height, xoff=0.5*trace_short+0.5*p.pad_width-0.5*p.trace_width,  yoff=-0.5*p.T_height)
            patch_L_R = draw.rectangle(p.pad_width, p.pad_height,  xoff=0.5*trace_long-0.5*p.pad_width+0.5*p.trace_width,  yoff=-0.5*p.T_height)
            patches = shapely.ops.unary_union([patch_L_L, patch_L_ML, patch_L_MR, patch_L_R, patch_U_L, patch_U_ML, patch_U_MR, patch_U_R])
            patches = patches.buffer(p.fillet_radius).buffer(-p.fillet_radius)
            patches = patches.buffer(-0.48*p.trace_width).buffer(0.48*p.trace_width)
        else: 
            patches = []

        # rotate and translate
        polys = [main_trace, pocket, pads_and_Ts, patches]
        polys = draw.rotate(polys, p.orientation, origin=(0, 0))
        polys = draw.translate(polys, p.pos_x, p.pos_y)
        [main_trace, pocket, pads_and_Ts, patches] = polys

        # subtract pocket
        self.add_qgeometry('poly', 
                           dict(pocket=pocket), 
                           subtract=True,
                           layer=p.layer)

        # add metals
        self.add_qgeometry('poly', 
                           dict(trace=main_trace, 
                                pads=pads_and_Ts
                                ), 
                           subtract=False,
                           layer=p.layer)
    
        # add patches
        if patches:
            self.add_qgeometry('poly', 
                           dict(patches=patches), 
                           subtract=False,
                           layer=p.patch_layer)
        
        

class Lollipop(QComponent):
    """
    A circle connected to a straigh wire with a pin (named "pin") at the end. Intended to be used as a charge line.
    Mostly copied from _FluxoniumPocket originally made by Figen YILMAZ and Christian Kraglund Andersen.

    Created by Alex Nguyen
    
               |                               |           ^
               |                               |           |
               |                               |           |
               |              | |   L          |           |----->  X
               |              | |   L          |    
               |              | |   L          |           x = (pox_x, pos_y)
               |              | |   L          |           L = length
               |              |_|   L          |           P = Pin 
               |             /   \             |           ^   
               |            |  x  |            |           |
               |             \   /             |
               |               -               |
               |               P               |
    
    
    """

    default_options=Dict(pos_x='0um', pos_y='0um', orientation=0,
                         length = '100um', cpw_width='cpw_width', cpw_gap='cpw_gap', radius='cpw_width', make_pocket=True)
    
    def make(self):
        """This is executed by the user to generate the qgeometry for the
        component."""
        p = self.p

        pos_x=p.pos_x
        pos_y=p.pos_y
        length=p.length
        cpw_width=p.cpw_width
        cpw_gap=p.cpw_gap
        radius=p.radius
        make_pocket=p.make_pocket


    # Define the geometry
        # Charge Line
        charge_line = draw.rectangle(cpw_width, length, 0, 0)
        charge_line_gap = draw.rectangle(cpw_width+2*cpw_gap, length+cpw_gap/2, 0, -cpw_gap/4)

        # Making the charge_line and charge_line_gap circle and union them to charge_line and it's gap
        charge_line_round = draw.Point(0., (-length)/2).buffer(radius)
        charge_line_gap_round = draw.Point(0., -(length+radius)/2.2).buffer((radius+2*cpw_gap))
        charge_line = draw.union(charge_line, charge_line_round)
        charge_line_gap = draw.union(charge_line_gap, charge_line_gap_round)

        # Charge Line CPW wire
        port_line = draw.LineString([(-cpw_width/2, length/2),
                                     (cpw_width/2, length/2)])
        
        # Position the charge_line, rotate and translate
        objects = [charge_line, charge_line_gap, port_line]
        objects = draw.scale(objects, 1, -1, origin=(0, 0))#Figen Yilmaz made an upside lollipop
        objects = draw.rotate(objects, p.orientation, origin=(0,0))
        objects = draw.translate(
            objects,
            pos_x,
            pos_y)
        [charge_line, charge_line_gap, port_line] = objects

        self.add_qgeometry('poly', {'charge_line': charge_line})
        if make_pocket:
            self.add_qgeometry('poly', {'charge_line_gap': charge_line_gap}, subtract=True)

        ############################################################

        # add pins
        port_line_cords = list(draw.shapely.geometry.shape(port_line).coords)
        port_line_cords = port_line_cords[::-1]# if loc_H==1 else port_line_cords[::-1]
        points = list(port_line_cords)
        self.add_pin('pin', 
                    points, cpw_width)
        
class Wire(QComponent):
    """
    A straight CPW with pins on both ends. 

    Created by Alex Nguyen
                               P1
                               _
               |              | |   L          |           |----->  X
               |              | |   L          |    
               |              | |   L          |           x = (pox_x, pos_y)
               |              | |   L          |           L = length
               |              |_|   L          |           P1 = Pin1
               |               P2              |           P2 = Pin2
    
    
    """

    default_options=Dict(pos_x='0um', pos_y='0um', orientation=0,
                         length = '100um', cpw_width='cpw_width', cpw_gap='cpw_gap')
    
    def make(self):
        """This is executed by the user to generate the qgeometry for the
        component."""
        p = self.p

        pos_x=p.pos_x
        pos_y=p.pos_y
        length=p.length
        cpw_width=p.cpw_width
        cpw_gap=p.cpw_gap


    # Define the geometry
        # Charge Line
        charge_line = draw.rectangle(cpw_width, length, 0, 0)
        charge_line_gap = draw.rectangle(cpw_width+2*cpw_gap, length, 0, 0)

        

        # For the pins
        port_line1 = draw.LineString([(-cpw_width/2, length/2),
                                     (cpw_width/2, length/2)])
        
        port_line2 = draw.LineString([(-cpw_width/2, -length/2),
                                     (cpw_width/2, -length/2)])
        
        # Position the charge_line, rotate and translate
        objects = [charge_line, charge_line_gap, port_line1, port_line2]
        objects = draw.rotate(objects, p.orientation, origin=(0, 0))
        objects = draw.translate(
            objects,
            pos_x,
            pos_y)
        [charge_line, charge_line_gap, port_line1, port_line2] = objects

        self.add_qgeometry('poly', {'charge_line': charge_line})
        self.add_qgeometry('poly', {'charge_line_gap': charge_line_gap}, subtract=True)

        ############################################################

        # add pins
        port_line_cords1 = list(draw.shapely.geometry.shape(port_line1).coords)
        port_line_cords1 = port_line_cords1# if loc_H==1 else port_line_cords[::-1]
        points1 = list(port_line_cords1)
        self.add_pin('pin1', 
                    points1, cpw_width)
        
        port_line_cords2 = list(draw.shapely.geometry.shape(port_line2).coords)
        port_line_cords2 = port_line_cords2[::-1]# if loc_H==1 else port_line_cords[::-1]
        points2 = list(port_line_cords2)
        self.add_pin('pin2', 
                    points2, cpw_width)


class WireMeander(QRoute):
    """Meandered CPW between two pins that solves for an exact (filleted) length and searches for a
    layout that fits. Similar in use to Qiskit-Metal's RouteMeander, but more robust:

        * Fillets are computed by this component (QUtilities.calc_lines_and_fillets_on_path) and
          drawn into the geometry, so the renderer never re-fillets it and the qiskit-metal
          "short segments ... fillet" warning cannot occur. Where corners are too close for the
          full radius, the radius is reduced locally instead of being left sharp.
        * total_length is the true length of the drawn (filleted) centre line.
        * The meander amplitude is solved numerically for the requested length.
        * If the first layout breaks a rule (fillet radius reduced below fillet_min, the path
          crossing itself, or overlapping a component in avoid_components), it tries other
          layouts: mirrored, biased to one side, fewer legs, tighter spacing. The first layout
          that passes is drawn.
        * If no layout can reach total_length (pins too far apart, or not enough room under
          max_amplitude), the build fails with a message giving the reachable length range.

    Inherits QRoute class.

    Layout:
        A lead of length start_straight leaves the start pin and one of end_straight leaves the end pin
        (along each pin's normal). Between the two lead tips (S and E), the meander has legs
        perpendicular to the line S->E, stacked along it every meander.spacing:

                     ______        ______
                    |      |      |      |                spacing  = centre-to-centre leg distance
            S ___   |      |      |      |   ___ E        amplitude = solved for total_length
                 |  |      |      |      |  |
                 |__|      |______|      |__|

    The CPW is given via:
        * trace_width, trace_gap - CPW dimensions
        * fillet            - Requested corner radius (use <= spacing/2 for semicircular U-turns)
        * fillet_min        - Smallest acceptable radius after local reduction ('' -> 0.99*fillet)
        * fillet_resolution - Points per fillet arc in the drawn geometry

    Length and leads:
        * total_length - Length of the filleted centre line from start pin to end pin
        * lead.start_straight, lead.end_straight - Straight sections off each pin (use >= fillet)

    Meander:
        * meander.spacing       - Distance between adjacent legs (centre-to-centre). Should be at
                                  least trace_width + 2*trace_gap (+ some ground in between).
        * meander.asymmetry     - Offset of the meander centre line from the line S->E
        * meander.max_amplitude - Maximum leg half-height ('' -> unlimited)
        * meander.search        - If True, also tries mirrored/one-sided layouts, fewer legs and
                                  tighter spacing (x0.75, x0.5; never below trace_width +
                                  2*trace_gap + clearance or 2*fillet_min)

    Snapping:
        * snap - If True (default), the meander runs along whichever of x or y has the longest
                 S->E projection (most room for legs) and a straight jog joins it to E, keeping
                 the route Manhattan. If False, it runs straight along S->E.

    Obstacles:
        * avoid_components - List of component names to keep clear of, or 'all' (every other
                             component). The two straight leads are not checked, so the
                             components at either end can be listed too (this stops the
                             meander folding back over them); make the leads long enough
                             to clear them.
        * clearance        - Minimum ground between this CPW's gap and any avoided geometry

    After building, the chosen layout is stored in self.route_info (legs, amplitude, bias, mirror,
    length, smallest fillet radius, issues, layouts tried).

    Pins:
        'start' and 'end' (as with all QRoutes).

    Default Options:
        * trace_width='10um', trace_gap='10um'
        * fillet='30um', fillet_min='', fillet_resolution=16
        * total_length='5mm'
        * lead=Dict(start_straight='100um', end_straight='50um')
        * meander=Dict(spacing='200um', asymmetry='0um', max_amplitude='', search=True)
        * avoid_components=[], clearance='10um'
        * snap=True
    """

    default_options = Dict(trace_width='10um',
                           trace_gap='10um',
                           fillet='30um',
                           fillet_min='',
                           fillet_resolution=16,
                           total_length='5mm',
                           lead=Dict(start_straight='100um', end_straight='50um'),
                           meander=Dict(spacing='200um', asymmetry='0um', max_amplitude='', search=True),
                           avoid_components=[],
                           clearance='10um',
                           snap=True)

    # Layouts to try, in order: (bias, mirror). bias shifts legs to one side of the S->E line
    # (0 = centred, +-0.8 = mostly on one side); mirror flips which side the first leg goes to.
    _SEARCH_LAYOUTS = [(0.0, 1), (0.0, -1), (0.5, 1), (0.5, -1), (-0.5, 1), (-0.5, -1),
                       (0.8, 1), (0.8, -1), (-0.8, 1), (-0.8, -1)]

    @staticmethod
    def _optional_length(val):
        """Parsed optional length -> positive float, or None when unset. Anything that is not a
        positive number counts as unset: '', None, or an empty Dict (which is what a qiskit Dict
        returns for a missing key)."""
        try:
            val = float(val)
        except (TypeError, ValueError):
            return None
        return val if val > 0 else None

    @staticmethod
    def _snap_axis(delta, start_dir):
        """x/y unit vector to meander along: the axis with the largest positive projection of
        delta (most room for legs). Near-ties (within 5%) go to the start lead's direction."""
        axes = [np.array(a, dtype=float) for a in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        proj = [float(np.dot(delta, a)) for a in axes]
        for a, pr in zip(axes, proj):
            if np.dot(a, start_dir) > 1 - 1e-9 and pr >= 0.95 * max(proj):
                return a
        return axes[int(np.argmax(proj))]

    def make(self):
        p = self.p
        start = self.set_pin("start")
        end = self.set_pin("end")
        precision = self.design.template_options.PRECISION

        r = p.fillet
        r_min = self._optional_length(p.fillet_min)
        if r_min is None:
            r_min = 0.99 * r
        max_amp = self._optional_length(p.meander.max_amplitude)
        target = p.total_length

        # Lead tips S, E and meander frame: u is the meander axis, v is perpendicular to it.
        # With snap, u is the x/y axis with the longest S->E projection. In this frame S=(0, 0)
        # and E=(D, h): the meander's last leg ends at height h, so no extra jog is needed.
        S = start.position + start.direction * p.lead.start_straight
        E = end.position + end.direction * p.lead.end_straight
        delta = E - S
        if np.linalg.norm(delta) < 10 ** (-precision):
            raise ValueError(f"{self.name}: the start and end lead tips coincide; change lead lengths.")
        if str(p.snap).lower() in ('true', '1'):
            u = self._snap_axis(delta, start.direction)
        else:
            u = delta / np.linalg.norm(delta)
        v = np.array([-u[1], u[0]])
        D = float(np.dot(delta, u))
        h = float(np.dot(delta, v))
        if abs(h) < 10 ** (-precision):
            h = 0.0

        # Leg margins at each end of the axis: room for 1 fillet, or 2 if there is a corner there too
        corner_S = np.dot(start.direction, u) < 1 - 1e-9
        corner_E = np.dot(-end.direction, u) < 1 - 1e-9
        margin_min = r * (1 + max(corner_S, corner_E))

        # A U-turn between legs can be at most a semicircle of radius spacing/2. If the requested
        # fillet is bigger, accept that reduction once here rather than failing every layout on it.
        base_spacing = p.meander.spacing
        if r_min > base_spacing / 2:
            self.logger.warning(f"{self.name}: fillet ({r:.4g}) > spacing/2 ({base_spacing / 2:.4g}); "
                                f"U-turns will use radius spacing/2. Reduce fillet or increase spacing.")
            r_min = 0.99 * base_spacing / 2

        # Spacings to try: the requested one, then tighter ones (search only) that still leave
        # ground between adjacent legs and room for full-radius U-turns
        min_spacing = max(p.trace_width + 2 * p.trace_gap + p.clearance, 2 * r_min)
        spacings = [base_spacing]
        if p.meander.search:
            spacings += [base_spacing * s for s in (0.75, 0.5) if base_spacing * s >= min_spacing]

        obstacles = self._get_obstacles(p)
        layouts = self._SEARCH_LAYOUTS if p.meander.search else self._SEARCH_LAYOUTS[:1]

        def assemble(local):
            local = np.asarray(local, dtype=float)
            world = S + np.outer(local[:, 0], u) + np.outer(local[:, 1], v)
            return np.vstack([start.position, world, end.position])

        def build(n_legs, amp, bias, mirror, spacing):
            # Built mirrored, then flipped back, so the end height h is the same in both cases
            local = self._meander_local_pts(D, n_legs, spacing, amp, bias, p.meander.asymmetry,
                                            mirror * h)
            local[:, 1] *= mirror
            return assemble(local)

        def length_of(pts):
            segs = QUtilities.calc_lines_and_fillets_on_path(pts, r, precision)
            return sum(s['dist'] for s in segs), segs

        tried, best, solved_any = 0, None, False
        straight_pts = assemble([(0.0, 0.0), (D, 0.0)] + ([(D, h)] if h else []))
        straight_len, _ = length_of(straight_pts)
        reach = [straight_len, straight_len]    # [shortest, longest] lengths seen, for errors

        for spacing in spacings:
            n_max = int(np.floor((D - 2 * margin_min) / spacing)) + 1 if D > 2 * margin_min else 0
            if n_max < 2 and spacing == base_spacing and D - 2 * margin_min >= 2 * r:
                spacing = D - 2 * margin_min    # squeeze in a single U-turn
                n_max = 2
            for bias, mirror in layouts:
                for n_legs in range(n_max, 1, -1):
                    amp_lo = r
                    amp_hi = max_amp if max_amp is not None else max(target, r)
                    len_lo = length_of(build(n_legs, amp_lo, bias, mirror, spacing))[0]
                    len_hi = length_of(build(n_legs, amp_hi, bias, mirror, spacing))[0]
                    reach = [min(reach[0], len_lo), max(reach[1], len_hi)]
                    if len_lo > target:
                        continue    # too long even at minimum amplitude: use fewer legs
                    if len_hi < target:
                        break       # too short even at max amplitude: fewer legs only gets shorter
                    amp = self._solve_amplitude(
                        lambda a: length_of(build(n_legs, a, bias, mirror, spacing))[0],
                        target, amp_lo, amp_hi, len_lo, len_hi)
                    pts = build(n_legs, amp, bias, mirror, spacing)
                    length, segs = length_of(pts)
                    issues = self._check_layout(p, pts, segs, r, r_min, spacing, obstacles, precision)
                    tried += 1
                    solved_any = True
                    info = Dict(n_legs=n_legs, amplitude=amp, bias=bias, mirror=mirror,
                                spacing=spacing, length=length, issues=issues, segs=segs, pts=pts)
                    if best is None or len(issues) < len(best.issues):
                        best = info
                    if not issues:
                        break
                if best is not None and not best.issues:
                    break
            if best is not None and not best.issues:
                break

        # A straight connection is fine if it already has the right length
        if (best is None or best.issues) and abs(straight_len - target) < 1e-6:
            pts = straight_pts
            length, segs = length_of(pts)
            best = Dict(n_legs=0, amplitude=0.0, bias=0.0, mirror=1, spacing=base_spacing,
                        length=length,
                        issues=self._check_layout(p, pts, segs, r, r_min, base_spacing, obstacles,
                                                  precision),
                        segs=segs, pts=pts)
            solved_any = True

        if not solved_any:
            units = self.design.get_units()
            raise ValueError(
                f"{self.name}: total_length={target:.4f}{units} cannot be reached. Reachable lengths "
                f"with these leads/spacing{'/max_amplitude' if max_amp is not None else ''} are "
                f"{reach[0]:.4f}-{reach[1]:.4f}{units} (lead tips are {np.linalg.norm(delta):.4f}{units} apart). "
                f"Move the pins, shorten the leads, or change spacing/max_amplitude.")

        if best.issues:
            self.logger.warning(f"{self.name}: no meander layout passed all checks after {tried} "
                                f"attempt(s); drawing the best one. Issues: {'; '.join(best.issues)}")

        # Draw the filleted centre line (no renderer filleting: fillet=0 in the geometry tables)
        fpts = QUtilities.calc_filleted_path(best.pts, r, precision, resolution=p.fillet_resolution)
        keep = np.r_[True, np.linalg.norm(np.diff(fpts, axis=0), axis=1) > 10 ** (-precision)]
        line = shapely.LineString(fpts[keep])
        self.add_qgeometry('path', {'trace': line}, width=p.trace_width, fillet=0, layer=p.layer)
        self.add_qgeometry('path', {'cut': line}, width=p.trace_width + 2 * p.trace_gap, fillet=0,
                           layer=p.layer, subtract=True)

        radii = [s['radius'] for s in best.segs if 'radius' in s]
        self._filleted_length = best.length
        self.options._actual_length = f"{best.length} {self.design.get_units()}"
        self.intermediate_pts = best.pts[2:-2]      # keeps QRoute.get_points() meaningful
        self.route_info = Dict(n_legs=best.n_legs, amplitude=best.amplitude, bias=best.bias,
                               mirror=best.mirror, spacing=best.spacing, length=best.length,
                               min_fillet=min(radii) if radii else None, issues=best.issues,
                               layouts_tried=tried)

    @property
    def length(self) -> float:
        """True length of the drawn (filleted) centre line."""
        return getattr(self, '_filleted_length', 0.0)

    @staticmethod
    def _meander_local_pts(D, n_legs, spacing, amp, bias, asymmetry, end_level=0.0):
        """Corner points in the (u, v) frame, from S=(0,0) to E=(D,end_level), with n_legs >= 2
        legs. Legs run between v=top and v=bot; the first leg starts on v=0 and the last leg
        ends on v=end_level."""
        top = asymmetry + amp * (1 + bias)
        bot = asymmetry - amp * (1 - bias)
        margin = (D - (n_legs - 1) * spacing) / 2
        xs = margin + spacing * np.arange(n_legs)

        pts = [(0.0, 0.0), (xs[0], 0.0), (xs[0], top)]
        level = top
        for k in range(1, n_legs - 1):
            pts.append((xs[k], level))
            level = bot if level == top else top
            pts.append((xs[k], level))
        pts += [(xs[-1], level), (xs[-1], end_level), (D, end_level)]
        return np.array(pts, dtype=float)

    @staticmethod
    def _solve_amplitude(length_fn, target, lo, hi, f_lo, f_hi, tol=1e-10, max_iter=100):
        """Solves length_fn(amp) == target on [lo, hi] (length grows with amplitude) using the
        Illinois false-position method. Length is piecewise linear in amplitude, so this usually
        converges in a few evaluations; the bracket guarantees convergence regardless."""
        g_lo, g_hi = f_lo - target, f_hi - target
        side = 0
        amp = lo
        for _ in range(max_iter):
            amp = (lo * g_hi - hi * g_lo) / (g_hi - g_lo) if g_hi != g_lo else 0.5 * (lo + hi)
            g = length_fn(amp) - target
            if abs(g) < tol or hi - lo < tol:
                break
            if g < 0:
                lo, g_lo = amp, g
                if side == -1:
                    g_hi *= 0.5
                side = -1
            else:
                hi, g_hi = amp, g
                if side == 1:
                    g_lo *= 0.5
                side = 1
        return amp

    def _get_obstacles(self, p):
        """Prepared union of the footprints of the components to avoid (or None)."""
        names = p.avoid_components
        if isinstance(names, str):
            if names.strip().lower() != 'all':
                names = [names]
            else:
                names = [n for n in self.design.components.keys() if n != self.name]
        shapes = []
        for name in names:
            if name not in self.design.components:
                self.logger.warning(f"{self.name}: avoid_components entry '{name}' is not in the design.")
                continue
            for kind in ('path', 'poly'):
                df = self.design.qgeometry.get_component(name, kind)
                if df is None:
                    continue
                for _, row in df.iterrows():
                    shapes.append(row.geometry.buffer(row.width / 2, cap_style=2) if kind == 'path'
                                  else row.geometry)
        if not shapes:
            return None
        union = shapely.unary_union(shapes)
        shapely.prepare(union)
        return union

    def _check_layout(self, p, pts, segs, r, r_min, spacing, obstacles, precision):
        """Human-readable list of problems with a candidate layout (empty = OK)."""
        issues = []
        radii = [s['radius'] for s in segs if 'radius' in s]
        if radii and min(radii) < r_min - 10 ** (-precision):
            issues.append(f"fillet reduced to {min(radii):.4g} (< fillet_min {r_min:.4g})")
        if spacing < p.trace_width + 2 * p.trace_gap:
            issues.append(f"spacing {spacing:.4g} < trace_width + 2*trace_gap: adjacent gaps merge")

        fpts = QUtilities.calc_filleted_path(pts, r, precision, resolution=4)
        centre = shapely.LineString(fpts)
        if not centre.is_simple:
            issues.append("path crosses itself")
        if obstacles is not None:
            # Skip the straight leads (minus the fillet that starts on them): they must touch the
            # components at each end, which can therefore be avoided like everything else. At
            # least the footprint half-width is always skipped, so the contact at each pin never
            # counts even when a lead is shorter than the fillet.
            half = p.trace_width / 2 + p.trace_gap + p.clearance
            s0 = max(p.lead.start_straight - r, half)
            s1 = centre.length - max(p.lead.end_straight - r, half)
            if s1 > s0:
                from shapely.ops import substring
                core = substring(centre, s0, s1)
                # (1nm less, so that merely touching an avoided shape does not count)
                footprint = core.buffer(half - 1e-6, cap_style=2)
                if obstacles.intersects(footprint):
                    issues.append("too close to an avoided component")
        return issues

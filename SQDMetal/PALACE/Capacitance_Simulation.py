# Copyright 2025 Prasanna Pakkiam
# SPDX-License-Identifier: Apache-2.0

from SQDMetal.PALACE.Model import PALACE_Model
from SQDMetal.COMSOL.Model import COMSOL_Model
from SQDMetal.COMSOL.SimCapacitance import COMSOL_Simulation_CapMats
from SQDMetal.Utilities.Materials import Material
from SQDMetal.Utilities.QubitDesigner import FloatingTransmonDesigner
import matplotlib.pyplot as plt
import json
import os
import gmsh
import shapely
import numpy as np
import pandas as pd
import geopandas as gpd
from SQDMetal.PALACE.Utilities.GMSH_Geometry_Builder import GMSH_Geometry_Builder
from SQDMetal.PALACE.Utilities.GMSH_Mesh_Builder import GMSH_Mesh_Builder
from SQDMetal.PALACE.PVDVTU_Viewer import PVDVTU_Viewer

class PALACE_Capacitance_Simulation(PALACE_Model):

    #Class Variables
    default_user_options = {
                 "fillet_resolution": 4,
                 "dielectric_material": "silicon",
                 "solns_to_save": -1,
                 "solver_order": 2,
                 "solver_tol": 1.0e-8,
                 "solver_maxits": 100,
                 "mesh_max": 100e-6,
                 "mesh_min": 10e-6,
                 "taper_dist_min": 30e-6,
                 "taper_dist_max": 200e-6,              
                 "gmsh_dist_func_discretisation": 130,
                 "HPC_Parameters_JSON": "",
                 "fuse_threshold": 1e-9,
                 "gmsh_verbosity": 1,
                 "threshold": 1e-9,
                 "simplify_edge_min_angle_deg": -1,
                 'palace_mode': 'local',
                 'palace_wsl_spack_repo_directory': '~/repo'
    }

    # Parent Directory path
    HPC_parent_simulation_dir = "C:/PALACE_Simulations/"
    simPC_parent_simulation_dir = "/home/experiment/PALACE/Simulations/input"

    #constructor
    def __init__(self, name, sim_parent_directory, mode, meshing, user_options = {}, 
                                    view_design_gmsh_gui = False, create_files = False, **kwargs):
        self.name = name
        self.sim_parent_directory = sim_parent_directory
        self.mode = mode
        self.meshing = meshing
        self.user_options = {}
        for key in PALACE_Capacitance_Simulation.default_user_options:
            self.user_options[key] = user_options.get(key, PALACE_Capacitance_Simulation.default_user_options[key])
        self.view_design_gmsh_gui = view_design_gmsh_gui
        self.create_files = create_files
        self._cur_cap_terminals = []
        self._num_conductors = 0
        self.cap_matrix = None
        super().__init__(meshing, mode, user_options, **kwargs)


    def prepare_simulation(self):
        '''set-up the simulation'''

        if self.meshing == 'GMSH':
            ggb = GMSH_Geometry_Builder(self._geom_processor, self.user_options['fillet_resolution'], self.user_options['gmsh_verbosity'])
            gmsh_render_attrs = ggb.construct_geometry_in_GMSH(self._metallic_layers, self._ground_plane, [],
                                                               self._fine_meshes, self.user_options["fuse_threshold"],
                                                               threshold=self.user_options["threshold"],
                                                               simplify_edge_min_angle_deg=self.user_options["simplify_edge_min_angle_deg"],
                                                               full_3D_params = self._full_3D_params,
                                                               boundary_distances = self._boundary_distances)
            #
            gmb = GMSH_Mesh_Builder(gmsh_render_attrs['fine_mesh_elems'], self.user_options)
            gmb.build_mesh()

            if self.create_files:
                #create directory to store simulation files
                self._create_directory(self.name)

                #create config file
                self.create_config_file(gmsh_render_attrs = gmsh_render_attrs)

                #create batch file
                # if self.mode == 'HPC':
                #     self.create_batch_file()

                self._save_mesh_gmsh()


            # abhishekchak52: commented out for now since pgr is not defined
            # if self.view_design_gmsh_gui:
            #     #plot design in gmsh gui
            #     pgr.view_design_components()
            
                   
        if self.meshing == 'COMSOL':

            #initialise the COMSOL engine
            COMSOL_Model.init_engine()
            cmsl = COMSOL_Model('res')

            #Create COMSOL capacitance sim object
            simCapMats = COMSOL_Simulation_CapMats(cmsl)
            cmsl.initialize_model(self._geom_processor.design, [simCapMats], bottom_grounded = True, resolution = 10)     #TODO: Make COMSOL actually compatible rather than assuming Qiskit-Metal designs?

            #Add metallic layers
            cmsl.add_metallic(1, threshold=1e-10, fuse_threshold=1e-10)
            cmsl.add_ground_plane(threshold=1e-10)
            #cmsl.fuse_all_metals()

            #build model
            cmsl.build_geom_mater_elec_mesh(mesh_structure = self.user_options["comsol_meshing"])

            #plot model
            cmsl.plot()

            #save comsol file
            #cmsl.save(self.name)

            if self.create_files:
                #create directory to store simulation files
                self._create_directory(self.name)

                #create config file
                self.create_config_file(comsol_obj = cmsl, simCap_object = simCapMats)

                #create batch file
                if self.mode == 'HPC':
                    self.create_batch_file()

            #save mesh
            self._save_mesh_comsol(comsol_obj = cmsl)

    def _create_directory(self, directory_name):
        '''create a directory to hold the simulation files'''

        if self.create_files:
            parent_simulation_dir = self._check_simulation_mode()

            # Directory
            directory = directory_name
    
            # Path
            path = os.path.join(parent_simulation_dir, directory)
    
            # Create the directory
            if not os.path.exists(path):
                os.mkdir(path)
                # print("Directory '% s' created" % directory)



    def _save_mesh_gmsh(self):

        parent_simulation_dir = self._check_simulation_mode()

        # file_name
        file_name = self.name + "/" + self.name + ".msh"
  
        # Path
        path = os.path.join(parent_simulation_dir, file_name)
        gmsh.write(path)
        


    def _save_mesh_comsol(self, comsol_obj):
        '''function used to save the comsol mesh file'''
        if self.create_files:
            parent_simulation_dir = self._check_simulation_mode()

            # file_name
            file_name = self.name + "/" + self.name + ".mphbin"
    
            # Path
            path = os.path.join(parent_simulation_dir, file_name)

            #COMSOL export commands
            comsol_obj._model.java.component("comp1").mesh("mesh1").export().set("filename", path)
            comsol_obj._model.java.component("comp1").mesh("mesh1").export(path)

    def display_conductor_indices(self, save=False):
        '''
        Plots a coloured visualisation of the metallic conductors and their corresponding row/column indices of the capacitance matrix.
        '''
        assert len(self._cur_cap_terminals) > 0, "There are no terminals. Ensure prepare_simulation() has been called."

        minX = (self._geom_processor.chip_centre[0] - self._geom_processor.chip_size_x*0.5)
        maxX = (self._geom_processor.chip_centre[0] + self._geom_processor.chip_size_x*0.5)
        minY = (self._geom_processor.chip_centre[1] - self._geom_processor.chip_size_y*0.5)
        maxY = (self._geom_processor.chip_centre[1] + self._geom_processor.chip_size_y*0.5)
        chip_bounding_poly = shapely.LineString([(minX,minY),(maxX,minY),(maxX,maxY),(minX,maxY),(minX,minY)])
        
        leGeoms = [chip_bounding_poly] + self._cur_cap_terminals
        leNames = ["Chip"] + [f"Cond{x+1}" for x in range(len(self._cur_cap_terminals))]
        gdf = gpd.GeoDataFrame({'names':leNames}, geometry=leGeoms)
        fig, ax = plt.subplots(1)
        gdf.plot(ax = ax, column='names', cmap='jet', alpha=0.5, categorical=True, legend=True)
        ax.set_xlabel('Position (m)')
        ax.set_ylabel('Position (m)')

        if save==True:
            fig.savefig("ConductorIndicides.png")


        return fig

    def create_config_file(self, **kwargs):
        '''create the configuration file which specifies the simulation type and the parameters'''    

        if self.meshing == 'GMSH':

            #GMSH renderer object needed to get boundary conditions for config file
            gmsh_render_attrs = kwargs['gmsh_render_attrs']

            #GMSH config file variables
            material_air = gmsh_render_attrs['air_box']
            material_dielectric = gmsh_render_attrs['dielectric']
            far_field = [gmsh_render_attrs['far_field'][x] for x in gmsh_render_attrs['far_field']]
            
            self._cur_cap_terminals = gmsh_render_attrs['metalsShapely']

            #metals to compute capacitances for
            Terminal = []
            for i,value in enumerate(gmsh_render_attrs['metals']):
                metal = {"Index": i+1,
                        "Attributes": [value]}
                Terminal.append(metal)

            #define length scale
            l0 = 1e-3

            #file extension
            file_ext = '.msh'
        
        if self.meshing == 'COMSOL':

            #COMSOL object and RF Sim object needed to get boundary conditions for config file
            comsol = kwargs['comsol_obj']  
            sCapMats = kwargs['simCap_object']

            #COMSOL config file variables
            material_air = list(comsol._model.java.component("comp1").material("Vacuum").selection().entities())
            material_dielectric = list(comsol._model.java.component("comp1").material("Substrate").selection().entities())
            far_field = list(comsol._model.java.component("comp1").physics(sCapMats.phys_es).feature("gnd1").selection().entities())

            self._cur_cap_terminals = [x[0] for x in sCapMats.model._cond_polys]

            #metals to compute capacitances for
            Terminal = []
            for i,term_name in enumerate(sCapMats.terminal_names):
                term_assigned_value = list(comsol._model.java.component("comp1").physics(sCapMats.phys_es).feature(term_name).selection().entities())
                metal = {"Index": i+1,
                        "Attributes": term_assigned_value}
                Terminal.append(metal)

            #define length scale
            l0 = 1

            #file extension
            file_ext = '.mphbin'

        #get material parameters
        dielectric = Material(self.user_options["dielectric_material"])

        
        #Define python dictionary to convert to json file
        if self._output_subdir == "":
            self.set_local_output_subdir("", False)
        filePrefix = self.hpc_options["input_dir"]  + self.name + "/" if self.hpc_options["input_dir"] != "" else ""
        self._mesh_name = filePrefix + self.name + file_ext
        post_procs = []
        for x in Terminal:
            post_procs.append({"Index":x["Index"], "Attributes":x["Attributes"], "Type": "Electric"})
        config = {
                    "Problem":
                    {
                        "Type": "Electrostatic",
                        "Verbose": 2,
                        "Output": filePrefix  + "outputFiles"
                    },
                    "Model":
                    {
                        "Mesh":  self._mesh_name,
                        "L0": l0,  # mm
                        "Refinement": self._mesh_refinement
                    },
                    "Domains":
                    {
                        "Materials":
                        [
                            {
                                "Attributes": material_air,  # Air
                                "Permeability": 1.0,
                                "Permittivity": 1.0,
                                "LossTan": 0.0
                            },
                            {
                                "Attributes": material_dielectric,  # Dielectric
                                "Permeability": dielectric.permeability,
                                "Permittivity": dielectric.permittivity,
                                "LossTan": dielectric.loss_tangent
                            }
                        ]
                    },
                    "Boundaries":
                    {
                        "Ground":
                        {
                        "Attributes": far_field
                        },
                        "Terminal":
                            Terminal,
                        "Postprocessing":  # Capacitance from charge instead of energy
                        {
                        "SurfaceFlux": post_procs,
                        }
                    },
                    "Solver":
                    {
                        "Order": self.user_options["solver_order"],
                        "Electrostatic":
                        {
                        "Save": len(Terminal) if self.user_options["solns_to_save"] == -1 else self.user_options["solns_to_save"]
                        },
                        "Linear":
                        {
                        "Type": "BoomerAMG",
                        "KSPType": "CG",
                        "Tol": self.user_options["solver_tol"],
                        "MaxIts": self.user_options["solver_maxits"]
                        }
                    }
                }

        #check simulation mode and return appropriate parent directory 
        parent_simulation_dir = self._check_simulation_mode()

        #destination for config file
        simulation_dir = parent_simulation_dir + str(self.name)

        #simulation file name
        sim_file_name = self.name+'.json'

        #save to created directory
        file = os.path.join(simulation_dir, sim_file_name)

        #write to file
        with open(file, "w+") as f:
            json.dump(config, f, indent=2)
        self.path_mesh = os.path.join(simulation_dir, self._mesh_name)
        self._sim_config = file
        self.set_local_output_subdir(self._output_subdir)

    def retrieve_data(self):
        raw_data = pd.read_csv(self._output_data_dir + '/terminal-C.csv')
        self.cap_matrix = raw_data
        headers = raw_data.columns # noqa: F841 # abhishekchak52: headers is not used
        raw_data = raw_data.to_numpy()[:,1:]    #First column is just the indices...

        fig = self.display_conductor_indices()
        fig.savefig(self._output_data_dir + '/terminal_indices.png')
        plt.close(fig)

        lePlots = self._output_data_dir + '/paraview/electrostatic/electrostatic.pvd'
        if os.path.exists(lePlots):
            leView = PVDVTU_Viewer(lePlots)
            for m in range(leView.num_datasets):
                try: 
                    leSlice = leView.get_data_slice(m)
                    fig = leSlice.plot(leSlice.get_data('V'), 'coolwarm', True)
                    fig.savefig(self._output_data_dir + f'/cond{m+1}_V.png')
                    plt.close(fig)
                except Exception as e:
                    print(f"Error in plotting: {e}")
            try:
                fig = leSlice.plot_mesh()
                fig.savefig(self._output_data_dir + '/mesh.png')
                plt.close(fig)
            except Exception as e:
                print(f"Error in plotting: {e}")

        return raw_data
    
    def floatingTransmon_calc_params(self, conductor_indices=None, print_all_capacitances=False, 
                                     res=None, qubit_freq=None, C_J=0, Z0_feedline=50):
        '''
        Calculate the charging energy E_C from the capacitance matrix
        for a floating transmon qubit. Can be either an isolated
        floating transmon or a floating transmon coupled to a resonator,
        depending on the number of conductors in the capacitance matrix.

        3 conductors: isolated floating transmon 
            (pad 1, pad 2, ground)
        4 conductors: floating transmon coupled to resonator
            (ground, pad 1, pad 2, resonator)
        5 conductors: floating transmon coupled to resonator-feedline
            (ground, pad 1, pad 2, resonator, feedline)

        '''
        # Constants
        e = 1.602176634e-19  # Coulombs
        h = 6.62607015e-34   # J·s     
        # Fetch capacitance matrix (if needed)
        if self.cap_matrix is None:
            raw_data = pd.read_csv(self._output_data_dir + '/terminal-C.csv')
            self.cap_matrix = raw_data
        capMat = self.cap_matrix.values
        if np.allclose(capMat[:,0], np.arange(1, capMat.shape[0]+1)):
            capMat = capMat[:, 1:]
        # detect number of conductors
        self._num_conductors = len(capMat[0])
        print(f"Proceeding with calculations for {self._num_conductors} conductors...\n")
        #default indeces
        default_indeces = {
            'ground': 0,
            'pad1': 1,
            'pad2': 2,
            'res': 3,
            'feed': 4
        }
        #Update indices if given
        if conductor_indices:
            default_indeces.update(conductor_indices)
        idx_ground = default_indeces['ground']
        idx_pad1   = default_indeces['pad1']
        idx_pad2   = default_indeces['pad2']
        idx_res    = default_indeces['res']
        idx_feed   = default_indeces['feed']

        # define ground and pad capacitance (all cases)
        C12 = abs(capMat[idx_pad1, idx_pad2])
        C1_ground  = abs(capMat[idx_pad1, idx_ground])
        C2_ground  = abs(capMat[idx_pad2, idx_ground])
        
        # 3 conductor case: qubit only
        if self._num_conductors == 3:
            C1_readout = 0
            C2_readout = 0
            C1_feed    = 0
            C2_feed    = 0
        # 4 conductors: qubit, res
        elif self._num_conductors == 4:
            C1_readout = abs(capMat[idx_pad1, idx_res])
            C2_readout = abs(capMat[idx_pad2, idx_res])
            C1_feed    = 0
            C2_feed    = 0
        # 5 conductors: qubit, res, feedline
        elif self._num_conductors == 5:
            C1_readout = abs(capMat[idx_pad1, idx_res])
            C2_readout = abs(capMat[idx_pad2, idx_res])
            C1_feed    = abs(capMat[idx_pad1, idx_feed])
            C2_feed    = abs(capMat[idx_pad2, idx_feed])
            # Resonator couplings (for kappa)
            C_rf       = abs(capMat[idx_res, idx_feed])
            C_rg       = abs(capMat[idx_res, idx_ground])
            C_rp1      = abs(capMat[idx_res, idx_pad1])
            C_rp2      = abs(capMat[idx_res, idx_pad2])
        
        ## CALCULATIONS
        # Calculate total C
        C_sigma = (((C1_ground+C1_readout)*(C2_ground+C2_readout)) \
                  / (C1_ground+C1_readout+C2_ground+C2_readout)) + C12 + C_J
        # Compute charging energy E_C
        E_C_J = e**2 / (2 * C_sigma)
        E_C_GHz = E_C_J / h / 1e9
        # Calculate qubit parameters (if possible)
        if (res is not None) and (self._num_conductors >= 4) and (qubit_freq is not None):
            # Use qubit calculator for chi, g, Delta etc.
            params = FloatingTransmonDesigner(res).optimise(
                {
                    "fQubit": qubit_freq,
                    "C_q1": C1_ground,
                    "C_q2": C2_ground,
                    "C_g1": C1_readout,
                    "C_g2": C2_readout,
                    "C_J": C12 + C_J,
                    "chi": (-1e6, -0.2e6),
                    "C_sigma": (1e-18, 1e-6),
                    "Ej/Ec": (50, 200),
                },
                print_results=False
            )
            g_MHz = -params['g_Hz'] * 1e-6
            chi_MHz = -params['chi_Hz'] * 1e-6
            Delta_GHz = params['Delta_Hz'] * 1e-9
            anh_MHz = params['anh_Hz'] * 1e-6
            f_r_Hz = res.get_res_frequency() # Hz
            # Calculate kappa, Purcell decay (if applicable)
            if self._num_conductors >= 5:
                C_r = C_rg + C_rp1 + C_rp2 # res capacitance (except feedline)
                C_c = C_rf # res-feedline mutual capacitance
                # External quality factor and linewidth (frequency units)
                Q_c = C_r / (2 * np.pi * f_r_Hz * Z0_feedline * C_c**2)
                kappa_MHz = f_r_Hz / Q_c * 1e-6
                T1p_ms = ((1 / (kappa_MHz*1e6)) * ((Delta_GHz * 1e9)**2 / (g_MHz*1e6)**2)) * 1e3
            else:
                kappa_MHz = None
                T1p_ms = None
        else:
            print("Could not calculate g, chi, kappa, or Purcell decay rate as there is no readout resonator present, or no defined qubit frequency.")
            g_MHz = 'N/A'
            chi_MHz = 'N/A'
            Delta_GHz = 'N/A'
            anh_MHz = 'N/A'
        
        # Calculate junction parameters for target frequency (if applicable)
        if qubit_freq:
            phi_0 = h / (2*e) 
            E_J_GHz = (h * qubit_freq + E_C_J)**2 / (8 * E_C_J) / h / 1e9
            L_J_nH = phi_0**2 / (4 * np.pi**2 * h * E_J_GHz)
        else:
            E_J_GHz = 'N/A'
            L_J_nH = 'N/A'

        if print_all_capacitances:
            print("Capacitance Results")
            print("--------------------")
            print(f"{'C1-Ground':<16s} = {C1_ground * 1e15:>10.3f} fF")
            print(f"{'C2-Ground':<16s} = {C2_ground * 1e15:>10.3f} fF")
            print(f"{'C1-Readout':<16s} = {C1_readout * 1e15:>10.3f} fF")
            print(f"{'C2-Readout':<16s} = {C2_readout * 1e15:>10.3f} fF")
            print(f"{'C1-Feedline':<16s} = {C1_feed * 1e15:>10.3f} fF")
            print(f"{'C2-Feedline':<16s} = {C2_feed * 1e15:>10.3f} fF")
            print(f"{'Mutual C12':<16s} = {C12 * 1e15:>10.3f} fF")
            print(f"{'C_sigma':<16s} = {C_sigma * 1e15:>10.1f} fF\n")

        # Print charging energy
        print("Circuit Parameters")
        print("-------------------")
        if (res is not None) and (qubit_freq is not None):
            print(f"{'f_res':<16s} = {f_r_Hz * 1e-9:>10.1f} GHz")
            print(f"{'f_qubit':<16s} = {qubit_freq * 1e-9:>10.1f} GHz")
        print(f"{'E_C':<16s} = {E_C_GHz * 1e3:>10.1f} MHz")
        print(f"{'g':<16s} = {g_MHz if isinstance(g_MHz, str) else f'{g_MHz:>10.3f}'} MHz")
        print(f"{'chi':<16s} = {chi_MHz if isinstance(chi_MHz, str) else f'{chi_MHz:>10.3f}'} MHz")
        print(f"{'Delta':<16s} = {Delta_GHz if isinstance(Delta_GHz, str) else f'{Delta_GHz:>10.3f}'} GHz")
        print(f"{'Anharmonicity':<16s} = {anh_MHz if isinstance(anh_MHz, str) else f'{anh_MHz:>10.3f}'} MHz")
        if kappa_MHz is not None:
            print(f"{'kappa':<16s} = {kappa_MHz:>10.1f} MHz")
            print(f"{'T_1,P':<16s} = {T1p_ms:>10.1f} ms")
        print()

        # Print required junction parameters for desired frequency
        if qubit_freq:
            print(f"Target Junction Parameters\n (for f_qubit = {qubit_freq * 1e-9:.1f} GHz)")
            print("--------------------------")
            print(f"{'E_J':<16s} = {E_J_GHz:>10.1f} GHz")
            print(f"{'L_J':<16s} = {L_J_nH:>10.1f} nH")

        return {
            # Energies and key circuit parameters
            "E_C_GHz": E_C_GHz,
            "C_sigma_fF": C_sigma * 1e15,
            "g_MHz": g_MHz,
            "chi_MHz": chi_MHz,
            "Delta_GHz": Delta_GHz,
            "anh_MHz": anh_MHz,

            # Individual capacitances
            "C1_ground_fF": C1_ground * 1e15,
            "C2_ground_fF": C2_ground * 1e15,
            "C1_readout_fF": C1_readout * 1e15,
            "C2_readout_fF": C2_readout * 1e15,
            "C1_feed_fF": C1_feed * 1e15,
            "C2_feed_fF": C2_feed * 1e15,
            "C12_fF": C12 * 1e15
        }


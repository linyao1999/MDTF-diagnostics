import os
import sys
import unittest
import mock # define mock os.environ so we don't mess up real env vars
import src.util_mdtf as util_mdtf
from src.data_manager import DataSet, DataManager
from src.datelabel import DateFrequency
from src.diagnostic import Diagnostic, PodRuntimeError
from tests.shared_test_utils import setUp_ConfigManager, tearDown_ConfigManager

class TestDiagnosticInit(unittest.TestCase):
    # pylint: disable=maybe-no-member
    default_pod_CF = {
        'settings':{}, 
        'varlist':[{'var_name': 'pr_var', 'freq':'mon'}]
        }
    dummy_paths = {
        'CODE_ROOT':'A', 'OBS_DATA_ROOT':'B', 'MODEL_DATA_ROOT':'C',
        'WORKING_DIR':'D', 'OUTPUT_DIR':'E'
    }
    dummy_var_translate = {
        'convention_name':'not_CF',
        'var_names':{'pr_var': 'PRECT', 'prc_var':'PRECC'}
    }

    @mock.patch('src.util_mdtf.util.read_json', return_value=dummy_var_translate)
    def setUp(self, mock_read_json):
        setUp_ConfigManager(
            paths=self.dummy_paths, 
            pods={'DUMMY_POD': self.default_pod_CF}
        )
        _ = util_mdtf.VariableTranslator(unittest = True)

    def tearDown(self):
        tearDown_ConfigManager()

    # ---------------------------------------------------  

    def test_parse_pod_settings(self):
        # normal operation
        config = util_mdtf.ConfigManager(unittest=True)
        config.pods['DUMMY_POD'] = {'settings':{'required_programs':'B'},'varlist':[]}
        pod = Diagnostic('DUMMY_POD')
        self.assertEqual(pod.name, 'DUMMY_POD')
        self.assertEqual(pod.required_programs, 'B')

    def test_parse_pod_varlist(self):
        # normal operation
        config = util_mdtf.ConfigManager(unittest=True)
        config.pods['DUMMY_POD'] = {
        'settings':{},'varlist':[{
                'var_name': 'pr_var', 'freq':'mon', 'requirement':'required'
            }]
        }
        pod = Diagnostic('DUMMY_POD')
        self.assertEqual(pod.varlist[0]['required'], True)

    def test_parse_pod_varlist_defaults(self):
        # fill in defaults
        config = util_mdtf.ConfigManager(unittest=True)
        config.pods['DUMMY_POD'] = {
        'settings':{},'varlist':[{
                'var_name': 'pr_var', 'freq':'mon', 'alternates':'foo'
            }]
        }
        test_ds = DataSet({
                'name':'foo', 'freq':'mon', 
                'CF_name':'foo', 'required': True,
                'original_name':'pr_var', 'alternates':[]
                })
        pod = Diagnostic('DUMMY_POD')
        self.assertEqual(pod.varlist[0]['required'], True)
        self.assertEqual(len(pod.varlist[0]['alternates']), 1)
        # self.assertDictEqual(pod.varlist[0]['alternates'][0].__dict__, test_ds.__dict__)

    def test_parse_pod_varlist_freq(self):
        config = util_mdtf.ConfigManager(unittest=True)
        config.pods['DUMMY_POD'] = {
        'settings':{},'varlist':[{
                'var_name': 'pr_var', 'freq':'not_a_frequency'
            }]
        }
        self.assertRaises(AssertionError, Diagnostic, 'A')


class TestDiagnosticSetUp(unittest.TestCase):
    # pylint: disable=maybe-no-member
    default_pod = {'settings':{}, 'varlist':[]}
    default_case = {
        'CASENAME': 'A', 'model': 'B', 'FIRSTYR': 1900, 'LASTYR': 2100,
        'pod_list': ['C']
    }
    dummy_paths = {
        'CODE_ROOT':'A', 'OBS_DATA_ROOT':'B', 'MODEL_DATA_ROOT':'C',
        'WORKING_DIR':'D', 'OUTPUT_DIR':'E'
    }
    dummy_var_translate = {
        'convention_name':'not_CF',
        'var_names':{'pr_var': 'PRECT', 'prc_var':'PRECC'}
    }

    @mock.patch('src.util_mdtf.util.read_json', return_value=dummy_var_translate)
    def setUp(self, mock_read_json):
        setUp_ConfigManager(
            config=self.default_case, 
            paths=self.dummy_paths, 
            pods={'DUMMY_POD': self.default_pod}
        )
        _ = util_mdtf.VariableTranslator(unittest = True)

    def tearDown(self):
        tearDown_ConfigManager()

    # ---------------------------------------------------  

    @unittest.skip("")
    @mock.patch.multiple(DataManager, __abstractmethods__=set())
    @mock.patch('os.path.exists', return_value = True)
    def test_set_pod_env_vars_paths(self, mock_exists):
        # check definition of pod paths
        case = DataManager(self.default_case)
        pod = Diagnostic('DUMMY_POD')
        case._setup_pod(pod)
        pod.POD_WK_DIR = 'A'
        pod._set_pod_env_vars()
        self.assertEqual(pod.pod_env_vars['POD_HOME'], 'TEST_CODE_ROOT/diagnostics/C')
        self.assertEqual(pod.pod_env_vars['OBS_DATA'], 'TEST_OBS_DATA_ROOT/C')
        self.assertEqual(pod.pod_env_vars['WK_DIR'], 'A')  

    @mock.patch('src.util_mdtf.check_dirs')
    @mock.patch('os.path.exists', return_value = False)
    @mock.patch('os.makedirs')
    def test_setup_pod_directories_mkdir(self, mock_makedirs, mock_exists, \
        mock_check_dirs): 
        # create output dirs if not present    
        pod = Diagnostic('DUMMY_POD')
        pod.POD_WK_DIR = 'A/B'
        pod._setup_pod_directories()
        mock_makedirs.assert_has_calls([
            mock.call('A/B/'+ s) for s in [
                '','model','model/PS','model/netCDF','obs','obs/PS','obs/netCDF'
            ]
        ], any_order = True)

    @mock.patch('os.path.exists', return_value = True)
    @mock.patch('os.makedirs')
    def test_setup_pod_directories_no_mkdir(self, mock_makedirs, mock_exists):
        # don't create output dirs if already present       
        pod = Diagnostic('DUMMY_POD')
        pod.POD_WK_DIR = 'A'
        pod._setup_pod_directories()
        mock_makedirs.assert_not_called()     

    @mock.patch('os.path.exists', return_value = True) 
    def test_check_pod_driver_no_driver_1(self, mock_exists):
        # fill in driver from pod name
        programs = util_mdtf.get_available_programs()
        pod = Diagnostic('DUMMY_POD')  
        pod._check_pod_driver()
        ext = os.path.splitext(pod.driver)[1][1:]
        self.assertTrue(ext in programs)
        self.assertEqual(pod.program, programs[ext])

    @mock.patch('os.path.exists', return_value = False)
    def test_check_pod_driver_no_driver_2(self, mock_exists):
        # assertion fails if no driver found
        pod = Diagnostic('DUMMY_POD')  
        self.assertRaises(PodRuntimeError, pod._check_pod_driver)


class TestDiagnosticCheckVarlist(unittest.TestCase):
    # pylint: disable=maybe-no-member
    default_pod = {'settings':{}, 'varlist':[]}
    dummy_paths = {
        'CODE_ROOT':'A', 'OBS_DATA_ROOT':'B', 'MODEL_DATA_ROOT':'C',
        'WORKING_DIR':'D', 'OUTPUT_DIR':'E'
    }
    dummy_var_translate = {
        'convention_name':'not_CF',
        'var_names':{'pr_var': 'PRECT', 'prc_var':'PRECC'}
    }

    @mock.patch('src.util_mdtf.util.read_json', return_value=dummy_var_translate)
    def setUp(self, mock_read_json):
        setUp_ConfigManager(
            paths=self.dummy_paths, 
            pods={'DUMMY_POD': self.default_pod}
        )
        _ = util_mdtf.VariableTranslator(unittest = True)

    def tearDown(self):
        tearDown_ConfigManager()

    # ---------------------------------------------------  

    def _populate_pod__local_data(self, pod):
        # reproduce logic in DataManager._setup_pod rather than invoke it here
        config = util_mdtf.ConfigManager(unittest = True)
        translate = util_mdtf.VariableTranslator(unittest = True)
        case_name = 'A'

        ds_list = []
        for var in pod.varlist:
            ds_list.append(DataSet.from_pod_varlist(
                pod.convention, var, {'DateFreqMixin': DateFrequency}))
        pod.varlist = ds_list

        for var in pod.iter_vars_and_alts():
            var.name_in_model = translate.fromCF('not_CF', var.CF_name)
            freq = var.date_freq.format_local()
            var._local_data = os.path.join(
                config.paths.MODEL_DATA_ROOT, case_name, freq,
                "{}.{}.{}.nc".format(
                    case_name, var.name_in_model, freq)
            )

    @mock.patch('os.path.isfile', return_value = True)
    def test_check_for_varlist_files_found(self, mock_isfile):
        # case file is found
        config = util_mdtf.ConfigManager(unittest=True)
        config.pods['DUMMY_POD'] = {
        'settings':{}, 'varlist':[
            {'var_name': 'pr_var', 'freq':'mon'}
        ]}
        pod = Diagnostic('DUMMY_POD') 
        self._populate_pod__local_data(pod)
        (found, missing) = pod._check_for_varlist_files(pod.varlist)
        self.assertEqual(found, ['TEST_MODEL_DATA_ROOT/A/mon/A.PRECT.mon.nc'])
        self.assertEqual(missing, [])

    @mock.patch('os.path.isfile', return_value = False)
    def test_check_for_varlist_files_not_found(self, mock_isfile):
        # case file is required and not found
        config = util_mdtf.ConfigManager(unittest=True)
        config.pods['DUMMY_POD'] = {
        'settings':{}, 'varlist':[
            {'var_name': 'pr_var', 'freq':'mon', 'required': True}
        ]}
        pod = Diagnostic('DUMMY_POD') 
        self._populate_pod__local_data(pod)
        (found, missing) = pod._check_for_varlist_files(pod.varlist)
        self.assertEqual(found, [])
        self.assertEqual(missing, ['TEST_MODEL_DATA_ROOT/A/mon/A.PRECT.mon.nc'])

    @mock.patch('os.path.isfile', side_effect = [False, True])
    def test_check_for_varlist_files_optional(self, mock_isfile):
        # case file is optional and not found
        config = util_mdtf.ConfigManager(unittest=True)
        config.pods['DUMMY_POD'] = {
        'settings':{}, 'varlist':[
            {'var_name': 'pr_var', 'freq':'mon', 'required': False}
        ]}
        pod = Diagnostic('DUMMY_POD') 
        self._populate_pod__local_data(pod)
        (found, missing) = pod._check_for_varlist_files(pod.varlist)
        self.assertEqual(found, [])
        self.assertEqual(missing, [])

    @mock.patch('os.path.isfile', side_effect = [False, True])
    def test_check_for_varlist_files_alternate(self, mock_isfile):
        # case alternate variable is specified and found
        config = util_mdtf.ConfigManager(unittest=True)
        config.pods['DUMMY_POD'] = {
        'settings':{}, 'varlist':[
            {'var_name': 'pr_var', 'freq':'mon', 
            'required': True, 'alternates':['prc_var']}
        ]}
        pod = Diagnostic('DUMMY_POD') 
        self._populate_pod__local_data(pod)
        (found, missing) = pod._check_for_varlist_files(pod.varlist)
        # name_in_model translation now done in DataManager._setup_pod
        self.assertEqual(found, ['TEST_MODEL_DATA_ROOT/A/mon/A.PRECC.mon.nc'])
        self.assertEqual(missing, [])


class TestDiagnosticSetUpCustomSettings(unittest.TestCase):
    # pylint: disable=maybe-no-member
    default_pod = {'settings':{}, 'varlist':[]}
    dummy_paths = {
        'CODE_ROOT':'A', 'OBS_DATA_ROOT':'B', 'MODEL_DATA_ROOT':'C',
        'WORKING_DIR':'D', 'OUTPUT_DIR':'E'
    }
    dummy_var_translate = {
        'convention_name':'not_CF',
        'var_names':{'pr_var': 'PRECT', 'prc_var':'PRECC'}
    }

    @mock.patch('src.util_mdtf.util.read_json', return_value=dummy_var_translate)
    def setUp(self, mock_read_json):
        setUp_ConfigManager(
            paths=self.dummy_paths, 
            pods={'DUMMY_POD': self.default_pod}
        )
        _ = util_mdtf.VariableTranslator(unittest = True)

    def tearDown(self):
        tearDown_ConfigManager()

    # ---------------------------------------------------  

    @mock.patch('os.path.exists', return_value = True)
    def test_set_pod_env_vars_vars(self, mock_exists):
        # check definition of additional env vars
        config = util_mdtf.ConfigManager(unittest=True)
        config.pods['DUMMY_POD'] = {
            'settings':{'pod_env_vars':{'D':'E'}}, 'varlist':[]
        }
        pod = Diagnostic('DUMMY_POD')
        pod.POD_WK_DIR = 'A'
        pod._set_pod_env_vars()
        self.assertEqual(os.environ['D'], 'E')
        self.assertEqual(pod.pod_env_vars['D'], 'E')

    @unittest.skip("")
    @mock.patch('os.path.exists', return_value = True)
    def test_check_pod_driver_program(self, mock_exists):
        # fill in absolute path and fill in program from driver's extension
        config = util_mdtf.ConfigManager(unittest=True)
        config.pods['DUMMY_POD'] = {
            'settings':{'driver':'C.ncl'}, 'varlist':[]
        }
        pod = Diagnostic('DUMMY_POD')  
        pod._check_pod_driver()
        self.assertEqual(pod.driver, 'TEST_CODE_ROOT/diagnostics/A/C.ncl')
        self.assertEqual(pod.program, 'ncl')

    @mock.patch('os.path.exists', return_value = True)
    def test_check_pod_driver_no_program_1(self, mock_exists):
        # assertion fail if can't recognize driver's extension
        config = util_mdtf.ConfigManager(unittest=True)
        config.pods['DUMMY_POD'] = {
            'settings':{'driver':'C.foo'}, 'varlist':[]
        }
        pod = Diagnostic('DUMMY_POD') 
        self.assertRaises(PodRuntimeError, pod._check_pod_driver)


class TestDiagnosticTearDown(unittest.TestCase):
    # pylint: disable=maybe-no-member
    default_pod = {'settings':{}, 'varlist':[]}
    dummy_paths = {
        'CODE_ROOT':'A', 'OBS_DATA_ROOT':'B', 'MODEL_DATA_ROOT':'C',
        'WORKING_DIR':'D', 'OUTPUT_DIR':'E'
    }
    dummy_var_translate = {
        'convention_name':'not_CF',
        'var_names':{'pr_var': 'PRECT', 'prc_var':'PRECC'}
    }

    @mock.patch('src.util_mdtf.util.read_json', return_value=dummy_var_translate)
    def setUp(self, mock_read_json):
        setUp_ConfigManager(
            paths=self.dummy_paths, 
            pods={'DUMMY_POD': self.default_pod}
        )
        _ = util_mdtf.VariableTranslator(unittest = True)

    def tearDown(self):
        tearDown_ConfigManager()

    # ---------------------------------------------------  

    # expected to fail because error will be raised about missing TEMP_HTML
    # attribute, which is set when PODs are initialized by data_manager
    @unittest.expectedFailure
    @mock.patch.dict('os.environ', {'CASENAME':'C'})
    @mock.patch('os.path.exists', return_value = True)
    @mock.patch('shutil.copy2')
    @mock.patch('os.system')
    @mock.patch('os.remove')
    @mock.patch('src.util.append_html_template')
    def test_make_pod_html(self, mock_append_html_template, mock_remove, \
        mock_system, mock_copy2, mock_exists): 
        pod = Diagnostic('DUMMY_POD')
        pod.MODEL_WK_DIR = '/B'
        pod.POD_WK_DIR = '/B/DUMMY_POD'
        pod._make_pod_html()
        mock_copy2.assert_has_calls([
            mock.call('TEST_CODE_ROOT/diagnostics/A/A.html', '/B/A'),
            mock.call('/B/A/tmp.html', '/B/A/A.html')
        ])
        mock_system.assert_has_calls([
            mock.call('cat /B/A/A.html | sed -e s/casename/C/g > /B/A/tmp.html')
        ])

    # ---------------------------------------------------

    @unittest.skip("")
    @mock.patch.dict('os.environ', {
        'convert_flags':'-C', 'convert_output_fmt':'png'
        })
    @mock.patch('glob.glob', return_value = ['A/model/PS/B.ps'])
    @mock.patch('subprocess.Popen')
    def test_convert_pod_figures(self, mock_subprocess, mock_glob):
        # assert we munged filenames correctly
        config = util_mdtf.ConfigManager(unittest=True)
        pod = Diagnostic('DUMMY_POD') 
        pod.POD_WK_DIR = 'A'  
        pod._convert_pod_figures(config)
        mock_system.assert_has_calls([
            mock.call('convert -C A/model/PS/B.ps A/model/B.png')
        ])

    # ---------------------------------------------------

    def test_cleanup_pod_files(self):
        pass

if __name__ == '__main__':
    unittest.main()
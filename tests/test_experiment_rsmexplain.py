import os
import tempfile
from os import getcwd
from os.path import join

from parameterized import param, parameterized

from rsmtool.configuration_parser import Configuration
from rsmtool.test_utils import check_run_explain, copy_data_files

# allow test directory to be set via an environment variable
# which is needed for package testing
TEST_DIR = os.environ.get("TESTDIR", None)
if TEST_DIR:
    rsmtool_test_dir = TEST_DIR
else:
    from rsmtool.test_utils import rsmtool_test_dir  # noqa: F401


@parameterized(
    [
        param("svr-explain", "svr"),
        param("knn-explain", "knn"),
        param("rf-explain", "rf"),
    ]
)
def test_run_experiment_parameterized(*args, **kwargs):
    if TEST_DIR:
        kwargs["given_test_dir"] = TEST_DIR
    check_run_explain(*args, **kwargs)


def test_run_experiment_svc_explain_with_object():
    """Test rsmexplain using a Configuration object, rather than a file."""
    source = "svr-explain-object"
    experiment_id = "svr_explain_object"

    configdir = join(rsmtool_test_dir, "data", "experiments", source)

    config_dict = {
        "description": "Explaning an SVR model trained on all features.",
        "experiment_dir": "existing_experiment",
        "experiment_id": "svr_explain_object",
        "background_data": "../../files/train.csv",
        "background_kmeans_size": 50,
        "explainable_data": "../../files/test.csv",
        "id_column": "ID",
        "sample_size": 10,
        "num_features_to_display": 15,
        "show_auto_cohorts": True,
    }

    config_obj = Configuration(config_dict, context="rsmexplain", configdir=configdir)

    check_run_explain(source, experiment_id, config_obj_or_dict=config_obj)


def test_run_experiment_svc_explain_with_dictionary():
    """Test rsmexplain using the dictionary object, rather than a file."""
    source = "svr-explain-dict"
    experiment_id = "svr_explain_dict"

    # set up a temporary directory since
    # we will be using getcwd
    temp_dir = tempfile.TemporaryDirectory(prefix=getcwd())

    old_file_dict = {
        "experiment_dir": "data/experiments/svr-explain-dict/existing_experiment",
        "background_data": "data/files/train.csv",
        "explainable_data": "data/files/test.csv",
    }

    new_file_dict = copy_data_files(temp_dir.name, old_file_dict, rsmtool_test_dir)

    config_dict = {
        "description": "Explaning an SVR model trained on all features.",
        "experiment_dir": new_file_dict["experiment_dir"],
        "experiment_id": "svr_explain_dict",
        "background_data": new_file_dict["background_data"],
        "background_kmeans_size": 50,
        "explainable_data": new_file_dict["explainable_data"],
        "id_column": "ID",
        "sample_size": 10,
        "num_features_to_display": 15,
        "show_auto_cohorts": True,
    }

    check_run_explain(source, experiment_id, config_obj_or_dict=config_dict)

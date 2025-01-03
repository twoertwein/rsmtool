"""
Configuration parser.

Classes related to parsing configuration files
and creating configuration objects.

:author: Jeremy Biggs (jbiggs@ets.org)
:author: Anastassia Loukina (aloukina@ets.org)
:author: Nitin Madnani (nmadnani@ets.org)

:organization: ETS
"""

from __future__ import annotations

import json
import logging
import re
import warnings
from collections import Counter
from copy import copy, deepcopy
from os import getcwd
from os.path import abspath
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

from sklearn.metrics import get_scorer_names
from skll.learner import Learner
from skll.metrics import _PREDEFINED_CUSTOM_METRICS

from .utils.constants import (
    BOOLEAN_FIELDS,
    CHECK_FIELDS,
    DEFAULTS,
    ID_FIELDS,
    LIST_FIELDS,
)
from .utils.files import parse_json_with_comments
from .utils.models import is_skll_model


def configure(
    context: str, config_file_or_obj_or_dict: Union[str, Configuration, Dict[str, Any], Path]
) -> Configuration:
    """
    Create a Configuration object.

    Get the configuration for ``context`` from the input
    ``config_file_or_obj_or_dict``.

    Parameters
    ----------
    context : str
        The context that is being configured. Must be one of
        "rsmtool", "rsmeval", "rsmcompare", "rsmsummarize",
        "rsmpredict", or "rsmxval".
    config_file_or_obj_or_dict : Union[str, Configuration, Dict[str, Any], Path]
        Path to the experiment configuration file either a a string
        or as a ``pathlib.Path`` object. Users can also pass a
        ``Configuration`` object that is in memory or a Python dictionary
        with keys corresponding to fields in the configuration file. Given a
        configuration file, any relative paths in the configuration file
        will be interpreted relative to the location of the file. Given a
        ``Configuration`` object, relative paths will be interpreted
        relative to the ``configdir`` attribute, that _must_ be set. Given
        a dictionary, the reference path is set to the current directory.

    Returns
    -------
    configuration : Configuration
        The Configuration object for the tool.

    Raises
    ------
    AttributeError
        If the ``configdir`` attribute for the Configuration input is not set.
    ValueError
        If ``config_file_or_obj_or_dict`` contains anything except a string,
        a path, a dictionary, or a ``Configuration`` object.
    """
    # check what sort of input we got
    # if we got a string we consider this to be path to config file
    if isinstance(config_file_or_obj_or_dict, (str, Path)):
        # Instantiate configuration parser object
        parser = ConfigurationParser(config_file_or_obj_or_dict)
        configuration = parser.parse(context=context)

    elif isinstance(config_file_or_obj_or_dict, dict):
        # directly instantiate the Configuration from the dictionary
        configuration = Configuration(config_file_or_obj_or_dict, context=context)

    elif isinstance(config_file_or_obj_or_dict, Configuration):
        # raise an error if we are passed a Configuration object
        # without a configdir attribute. This can only
        # happen if the object was constructed using an earlier version
        # of RSMTool and stored
        try:
            assert config_file_or_obj_or_dict.configdir is not None
        except AssertionError:
            raise AttributeError("Configuration object must have configdir attribute.")
        else:
            configuration = config_file_or_obj_or_dict

    else:
        raise ValueError(
            f"The input to run_experiment must be a path to the file (str), "
            f"a dictionary, or a configuration object. You passed "
            f"{type(config_file_or_obj_or_dict)}."
        )

    return configuration


class Configuration:
    """
    Configuration class.

    Encapsulates all of the configuration parameters and methods to
    access these parameters.
    """

    def __init__(
        self,
        configdict: Dict[str, Any],
        *,
        configdir: Optional[Union[str, Path]] = None,
        context: str = "rsmtool",
        logger: Optional[logging.Logger] = None,
    ):
        """
        Create an object of the `Configuration` class.

        This method can be used to directly instantiate a Configuration
        object.

        Parameters
        ----------
        configdict : Dict[str, Any]
            A dictionary of configuration parameters.
            The dictionary must be a valid configuration dictionary
            with default values filled as necessary.
        configdir : Optional[Union[str, Path]]
            The reference path used to resolve any relative paths
            in the configuration object. When ``None``, will be set during
            initialization to the current working directory.
            Defaults to ``None``,
        context : str
            The context of the tool. One of {"rsmtool", "rsmeval", "rsmcompare",
            "rsmpredict", "rsmsummarize"}.
            Defaults to "rsmtool".
        logger : Optional[logging.Logger]
            A Logger object. If ``None`` is passed, get logger from ``__name__``.
            Defaults to ``None``.
        """
        if not isinstance(configdict, dict):
            raise TypeError("The input must be a dictionary.")

        # create a logger instance
        self.logger = logger if logger else logging.getLogger(__name__)

        # process and validate the configuration dictionary
        configdict = ConfigurationParser.process_config(configdict)
        configdict = ConfigurationParser.validate_config(configdict, context=context)

        # set final config dir to `cwd` if not given and let the user know
        if configdir is None:
            final_configdir = Path(getcwd())
            self.logger.info(f"Configuration directory will be set to {final_configdir}")
        else:
            final_configdir = Path(configdir).resolve()

        self._config = configdict
        self._configdir = final_configdir
        self._context = context

    def __contains__(self, key: str) -> bool:
        """
        Check if the configuration object contains a given key.

        Parameters
        ----------
        key : str
            Key to check in the Configuration object.

        Returns
        -------
        key_check : bool
            ``True`` if key is in configuration object, else ``False``.
        """
        return key in self._config

    def __getitem__(self, key: str) -> Any:
        """
        Get configuration value for the given key.

        Parameters
        ----------
        key : str
            Key to check in the configuration object

        Returns
        -------
        value
            The value in the configuration object dictionary.
        """
        return self._config[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Set configuration value for the given key.

        Parameters
        ----------
        key : str
            Key to set in the configuration object.
        value
            The value to be set for the key.
        """
        self._config[key] = value

    def __len__(self) -> int:
        """
        Return the size of the configuration dictionary.

        Returns
        -------
        size : int
            The number of elements in the configuration dictionary.
        """
        return len(self._config)

    def __str__(self) -> str:
        """
        Return string representation of the configuration dictionary.

        Returns
        -------
        config_string : str
            A string representation of the underlying configuration
            dictionary as encoded by ``json.dumps()``. It only
            includes the configuration options that can be set by
            the user.
        """
        expected_fields = (
            CHECK_FIELDS[self._context]["required"] + CHECK_FIELDS[self._context]["optional"]
        )

        output_config = {k: v for k, v in self._config.items() if k in expected_fields}
        return json.dumps(output_config, indent=4, separators=(",", ": "))

    def __iter__(self) -> Generator[str, None, None]:
        """
        Iterate through configuration object keys.

        Yields
        ------
        key : str
            A key in the config dictionary
        """
        for key in self.keys():
            yield key

    @property
    def configdir(self) -> str:
        """
        Get the path to configuration directory.

        Get the path to the configuration reference directory that
        will be used to resolve any relative paths in
        the configuration.

        Returns
        -------
        configdir : str
            The path to the configuration reference directory.
        """
        return str(self._configdir)

    @configdir.setter
    def configdir(self, new_path: str) -> None:
        """
        Set a new configuration reference directory.

        Parameters
        ----------
        new_path : str
            Path to the new configuration reference
            directory used to resolve any relative paths
            in the configuration object.
        """
        if new_path is None:
            raise ValueError("The `configdir` attribute cannot be set to `None` ")

        # TODO: replace `Path(abspath(new_path))` with `Path(new_path).resolve()
        # once this Windows bug is fixed: https://bugs.python.org/issue38671
        self._configdir = Path(abspath(new_path))

    @property
    def context(self) -> str:
        """Get the context."""
        return self._context

    @context.setter
    def context(self, new_context: str) -> None:
        """
        Set a new context.

        Parameters
        ----------
        new_context : str
            A new context for the configuration object.
        """
        self._context = new_context

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value or default for the given key.

        Parameters
        ----------
        key : str
            Key to check in the Configuration object.
        default : Any
            The default value to return, if no key exists.
            Defaults to ``None``.

        Returns
        -------
        value
            The value in the configuration object dictionary.
        """
        return self._config.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """
        Get a dictionary representation of the configuration object.

        Returns
        -------
        config : Dict[str, Any]
            The configuration dictionary.
        """
        return self._config

    def keys(self) -> List[str]:
        """
        Return keys as a list.

        Returns
        -------
        keys : List[str]
            A list of keys in the configuration object.
        """
        return [k for k in self._config.keys()]

    def values(self) -> List[Any]:
        """
        Return configuration values as a list.

        Returns
        -------
        values : List[Any]
            A list of values in the configuration object.
        """
        return [v for v in self._config.values()]

    def items(self) -> List[Tuple[str, Any]]:
        """
        Return configuration items as a list of tuples.

        Returns
        -------
        items : List[Tuple[str, Any]]
            A list of (key, value) tuples in the configuration object.
        """
        return [(k, v) for k, v in self._config.items()]

    def pop(self, key: str, default: Any = None) -> Any:
        """
        Remove and return an element from the object having the given key.

        Parameters
        ----------
        key : str
            Key to pop in the configuration object.
        default: Any
            The default value to return, if no key exists.
            Defaults to ``None``.

        Returns
        -------
        value : Any
            The value removed from the object.
        """
        return self._config.pop(key, default)

    def copy(self, deep: bool = True) -> Configuration:
        """
        Return a copy of the object.

        Parameters
        ----------
        deep : bool
            Whether to perform a deep copy.
            Defaults to ``True``.

        Returns
        -------
        copy : Configuration
            A new configuration object.
        """
        if deep:
            return deepcopy(self)
        return copy(self)

    def save(self, output_dir: Optional[str] = None) -> None:
        """
        Save the configuration file to the output directory specified.

        Parameters
        ----------
        output_dir : Optional[str]
            The path to the output directory. If ``None``, the current directory
            is used.
            Defaults to ``None``.
        """
        # use the current working directory if no output directory is specified
        final_output_dir = Path(output_dir).resolve() if output_dir else Path(getcwd())

        # Create sub-directory for the output files, if it does not exist
        output_files_dir = Path(final_output_dir).resolve() / "output"
        output_files_dir.mkdir(parents=True, exist_ok=True)

        id_field = ID_FIELDS[self._context]
        experiment_id = self._config[id_field]
        context = self._context
        outjson = output_files_dir / f"{experiment_id}_{context}.json"

        with outjson.open(mode="w") as outfile:
            outfile.write(str(self))

    def check_exclude_listwise(self) -> bool:
        """
        Check for candidate exclusion.

        Check if we are excluding candidates based on number of responses, and
        add this to the configuration file.

        Returns
        -------
        exclude_listwise : bool
            Whether to exclude list-wise.
        """
        exclude_listwise = False
        if self._config.get("min_items_per_candidate"):
            exclude_listwise = True
        return exclude_listwise

    def check_flag_column(
        self, flag_column: str = "flag_column", partition: str = "unknown"
    ) -> Dict[str, List[str]]:
        """
        Make sure the column name in ``flag_column`` is correctly specified.

        Get flag columns and values for filtering, if any, and convert single
        values to lists. Raises an exception if the column name in ``flag_column``
        is not correctly specified in the configuration file.

        Parameters
        ----------
        flag_column : str
            The flag column name to check. Currently used names are
            "flag_column" or "flag_column_test".
            Defaults to "flag_column".

        partition: str
            The data partition which is filtered based on the flag column name.
            One of {"train", "test", "both", "unknown"}.
            Defaults to "unknown".

        Returns
        -------
        new_filtering_dict : Dict[str, List[str]]
            Properly formatted dictionary for the column name in ``flag_column``.

        Raises
        ------
        ValueError
            If the specified value of the column name in ``flag_column``
            is not a dictionary.
        ValueError
            If the value of ``partition`` is not in the expected list.
        ValueError
            If the value of ``partition`` does not match the ``flag_column``.
        """
        config = self._config

        new_filter_dict = {}

        flag_message = {
            "train": "training",
            "test": "evaluating",
            "both": "training and evaluating",
            "unknown": "training and/or evaluating",
        }

        if partition not in flag_message:
            raise ValueError(
                f"Unknown value for partition: {partition} This must "
                f"be one of the following: {','.join(flag_message.keys())}."
            )

        if flag_column == "flag_column_test":
            if partition in ["both", "train"]:
                raise ValueError(
                    "Conditions specified in 'flag_column_test' "
                    "can only be applied to the evaluation partition."
                )

        if config.get(flag_column):
            original_filter_dict = config[flag_column]

            # first check that the value is a dictionary
            if not isinstance(original_filter_dict, dict):
                raise ValueError(
                    "`flag_column` must be a dictionary. "
                    "Please refer to the documentation for "
                    "further information."
                )

            for column in original_filter_dict:
                # if we were given a single value, convert it to list
                if not isinstance(original_filter_dict[column], list):
                    new_filter_dict[column] = [original_filter_dict[column]]
                    self.logger.warning(
                        f"The filtering condition {original_filter_dict[column]} "
                        f"for column {column} was converted to list. Only "
                        f"responses where {column} == {original_filter_dict[column]} "
                        f"will be used for {flag_message[partition]} the model. "
                        f"You can ignore this warning if this is the correct "
                        f"interpretation of your configuration settings."
                    )
                else:
                    new_filter_dict[column] = original_filter_dict[column]

                    model_eval = ", ".join(map(str, original_filter_dict[column]))
                    self.logger.info(
                        f"Only responses where {column} equals one of the "
                        f"following values will be used for "
                        f"{flag_message[partition]} the model: {model_eval}."
                    )
        return new_filter_dict

    def get_trim_min_max_tolerance(
        self,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Get trim min, trim max, and tolerance values.

        Get the specified trim min and max, and trim_tolerance if any,
        and make sure they are numeric.

        Returns
        -------
        spec_trim_min : Optional[float]
            Specified trim min value.
        spec_trim_max : Optional[float]
            Specified trim max value.
        spec_trim_tolerance: Optional[float]
            Specified trim tolerance value.
        """
        config = self._config

        spec_trim_min = config.get("trim_min", None)
        spec_trim_max = config.get("trim_max", None)
        spec_trim_tolerance = config.get("trim_tolerance", None)

        if spec_trim_min:
            spec_trim_min = float(spec_trim_min)
        if spec_trim_max:
            spec_trim_max = float(spec_trim_max)
        if spec_trim_tolerance:
            spec_trim_tolerance = float(spec_trim_tolerance)
        return (spec_trim_min, spec_trim_max, spec_trim_tolerance)

    def get_rater_error_variance(self) -> float:
        """
        Get specified rater error variance, if any, and make sure it's numeric.

        Returns
        -------
        rater_error_variance : float
            Specified rater error variance.
        """
        config = self._config

        rater_error_variance = config.get("rater_error_variance", None)

        if rater_error_variance:
            rater_error_variance = float(rater_error_variance)

        return rater_error_variance

    def get_default_converter(self) -> Dict[str, Any]:
        """
        Get default converter dictionary for data reader.

        Returns
        -------
        default_converter : Dict[str, Any]
            The default converter for a train or test file.
        """
        string_columns = [self._config["id_column"]]

        candidate = self._config.get("candidate_column")
        if candidate is not None:
            string_columns.append(candidate)

        subgroups = self._config.get("subgroups")
        if subgroups:
            string_columns.extend(subgroups)

        return dict([(column, str) for column in string_columns if column])

    def get_names_and_paths(self, keys: List[str], names: List[str]) -> Tuple[List[str], List[str]]:
        """
        Get values (paths) for the given keys and names.

        This method is mainly used to retrieve values that are paths and
        it skips any values that are ``None``.

        Parameters
        ----------
        keys : List[str]
            A list of keys whose values to retrieve.
        names : List[str]
            The names corresponding to the keys.

        Returns
        -------
        existing_names : List[str]
            The names for values that were not ``None``.
        existing_paths : List[str]
            The paths (values) for the given keys (that were not ``None``.

        Raises
        ------
        ValueError
            If there are any duplicate keys or names.
        """
        assert len(keys) == len(names)

        # Make sure keys are not duplicated
        if not len(set(keys)) == len(keys):
            raise ValueError(
                f"The ``keys`` must be unique. However, the following "
                f"duplicate keys were found: "
                f"{', '.join([key for key, val in Counter(keys).items() if val > 1])}."
            )
        # Make sure names are not duplicated
        if not len(set(names)) == len(names):
            raise ValueError(
                f"The``names`` must be unique. However, the following "
                f"duplicate names were found: "
                f"{', '.join([name for name, val in Counter(names).items() if val > 1])}."
            )
        existing_names = []
        existing_paths = []
        for idx, key in enumerate(keys):
            path = self._config.get(key)

            # if the `features` field is a list, do not include it in the container
            if key == "features":
                if isinstance(path, list):
                    continue

            if path is not None:
                existing_paths.append(path)
                existing_names.append(names[idx])

        return existing_names, existing_paths


class ConfigurationParser:
    """``ConfigurationParser`` class to create ``Configuration`` objects."""

    # initialize class logger attribute to None
    logger = None

    def __init__(self, pathlike: Union[str, Path], logger: Optional[logging.Logger] = None):
        """
        Instantiate a ``ConfigurationParser`` for a given config file path.

        Parameters
        ----------
        pathlike : Union[str, Path]
            A string containing the path to the configuration file
            that is to be parsed. A ``pathlib.Path`` instance is also
            acceptable.
        logger : Optional[logging.Logger]
            Custom logger object to use, if not ``None``. Otherwise
            a new logger is created.
            Defaults to ``None``.

        Raises
        ------
        FileNotFoundError
            If the given path does not exist.
        OSError
            If the given path is a directory, not a file.
        ValueError
            If the file at the given path does not have
            a valid extension (".json").
        """
        # if we passed in a string, convert it to a Path
        if isinstance(pathlike, str):
            pathlike = Path(pathlike)

        # raise an exception if the file does not exist
        if not pathlike.exists():
            raise FileNotFoundError(f"The configuration file {pathlike} " f"was not found.")

        # raise an exception if the user specified a directory
        if not pathlike.is_file():
            raise OSError(f"The given path {pathlike} should be a " f"file, not a directory.")

        # make sure we have a file that ends in ".json"
        extension = pathlike.suffix.lower()
        if extension != ".json":
            raise ValueError(
                f"The configuration file must be in `.json` " f"format. You specified: {extension}."
            )

        # set the various attributes to None
        self._filename = pathlike.name
        self._configdir = pathlike.resolve().parent

        # set the `logger` class attribute to the given logger, if provided
        # or else create a new logger
        self.__class__.logger = logger if logger else logging.getLogger(__name__)

    @staticmethod
    def _fix_json(json_string: str) -> str:
        """
        Fix potential issues in configuration JSON.

        Take a JSON string that might have bad quotes or capitalized booleans
        and fix such issues so that the JSON can be parsed.

        Parameters
        ----------
        json_string : str
            A string to be reformatted for JSON parsing.

        Return
        ------
        json_string : str
            The updated string.
        """
        json_string = json_string.replace("True", "true")
        json_string = json_string.replace("False", "false")
        json_string = json_string.replace("'", '"')
        return json_string

    def _parse_json_file(self, filepath: Path) -> Dict[str, Any]:
        """
        Parse the configuration JSON.

        A private method to parse JSON configuration files and return
        a Python dictionary.

        Parameters
        ----------
        filepath : Path
            A ``pathlib.Path`` object containing the JSON configuration filepath.

        Returns
        -------
        configdict : Dict[str, Any]
            A Python dictionary containing the parameters from the
            JSON configuration file.

        Raises
        ------
        ValueError
            If the JSON file could not be parsed.
        """
        try:
            configdict = parse_json_with_comments(filepath)
        except ValueError:
            raise ValueError(
                f"The main configuration file `{filepath}` exists but "
                f"is formatted incorrectly. Please check that each "
                f"line ends with a comma, there is no comma at the end "
                f"of the last line, and that all quotes match."
            )

        return configdict

    def parse(self, context: str = "rsmtool") -> Configuration:
        """
        Parse configuration file.

        Parse the configuration file for which this parser was
        instantiated.

        Parameters
        ----------
        context : str
            Context of the tool in which we are validating. One of:
            {"rsmtool", "rsmeval", "rsmpredict", "rsmcompare",
            "rsmsummarize", "rsmxval", "rsmexplain"}.
            Defaults to "rsmtool".

        Returns
        -------
        configuration : Configuration
            A configuration object containing the parameters in the
            file that we instantiated the parser for.
        """
        filepath = self._configdir / self._filename
        configdict = self._parse_json_file(filepath)

        # create a new Configuration object which will automatically
        # process and validate the configuration
        # dictionary being passed in
        return Configuration(configdict, configdir=self._configdir, context=context)

    @classmethod
    def validate_config(cls, config: Dict[str, Any], context: str = "rsmtool") -> Dict[str, Any]:
        """
        Validate the given configuration dictionary.

        Ensure that all required fields are specified, add default values
        values for all unspecified fields, and ensure that all specified
        fields are valid.

        Parameters
        ----------
        config : Dict[str, Any]
            Given configuration dictionary to be validated.
        context : str
            Context of the tool in which we are validating.
            One of {"rsmtool", "rsmeval", "rsmpredict",
            "rsmcompare", "rsmsummarize"}.
            Defaults to "rsmtool".

        Returns
        -------
        new_config : Dict[str, Any]
            A copy of the given configuration dictionary with all required
            fields specified and with the default values for unspecified
            fields.

        Raises
        ------
        ValueError
            If the Configuration object does not contain all required fields,
            has any unrecognized fields, or has any fields with invalid values.
        """
        # make a copy of the given parameter dictionary
        new_config = deepcopy(config)

        # 1. Check to make sure all required fields are specified
        required_fields = CHECK_FIELDS[context]["required"]

        for field in required_fields:
            if field not in new_config:
                raise ValueError(f"The config file must specify '{field}'")

        # 2. Add default values for unspecified optional fields
        # for given RSMTool context
        defaults = DEFAULTS

        for field in defaults:
            if field not in new_config:
                new_config[field] = defaults[field]

        # 3. Check to make sure no unrecognized fields are specified
        for field in new_config:
            if field not in defaults and field not in required_fields:
                raise ValueError(f"Unrecognized field '{field}' in json file")

        # 4. Check to make sure that the ID fields that will be
        # used as part of filenames are formatted correctly
        # i.e., they do not contain any spaces and are < 200 characters
        id_field = ID_FIELDS[context]
        id_field_values = {id_field: new_config[id_field]}

        for id_field, id_field_value in id_field_values.items():
            if len(id_field_value) > 200:
                raise ValueError(f"{id_field} is too long (must be <=200 characters)")

            if re.search(r"\s", id_field_value):
                raise ValueError(f"{id_field} cannot contain any spaces")

        # 5. Check that the feature file and feature subset/subset file are not
        # specified together
        msg = (
            'You cannot specify BOTH "features" and "{}". '
            'Please refer to the "Selecting Feature Columns" '
            "section in the documentation for more details."
        )
        if new_config["features"] and new_config["feature_subset_file"]:
            msg = msg.format("feature_subset_file")
            raise ValueError(msg)
        if new_config["features"] and new_config["feature_subset"]:
            msg = msg.format("feature_subset")
            raise ValueError(msg)

        # 6. Check for fields that require feature_subset_file and try
        # to use the default feature file
        if new_config["feature_subset"] and not new_config["feature_subset_file"]:
            raise ValueError(
                "If you want to use feature subsets, you " "must specify a feature subset file"
            )

        if new_config["sign"] and not new_config["feature_subset_file"]:
            raise ValueError(
                "If you want to specify the expected sign of "
                "correlation for each feature, you must "
                "specify a feature subset file"
            )

        # 7. Check for fields that must be specified together
        if new_config["min_items_per_candidate"] and not new_config["candidate_column"]:
            raise ValueError(
                "If you want to filter out candidates with "
                "responses to less than X items, you need "
                "to specify the name of the column which "
                "contains candidate IDs."
            )

        # 8. Check that if "skll_objective" is specified, it's
        # one of the metrics that SKLL allows for AND that it is
        # specified for a SKLL model and _not_ a built-in
        # linear regression model
        if new_config["skll_objective"]:
            if not is_skll_model(new_config["model"]):
                warnings.warn(
                    "You specified a custom SKLL objective but also chose a "
                    "non-SKLL model. The objective will be ignored."
                )
            else:
                if (
                    new_config["skll_objective"] not in get_scorer_names()
                    and new_config["skll_objective"] not in _PREDEFINED_CUSTOM_METRICS
                ):
                    raise ValueError(
                        "Invalid SKLL objective. Please refer to the SKLL "
                        "documentation and choose a valid tuning objective."
                    )

        # 9. Check that if "skll_fixed_parameters" is specified,
        # it's specified for SKLL model and _not_ a built-in linear
        # regression model; we cannot check whether the parameters
        # are valid at parse time but SKLL will raise an error
        # at run time for any invalid parameters
        if new_config["skll_fixed_parameters"]:
            if not is_skll_model(new_config["model"]):
                warnings.warn(
                    "You specified custom SKLL fixed parameters but "
                    "also chose a non-SKLL model. The parameters will "
                    "be ignored."
                )

        # 10. Check that if we are running rsmtool to ask for
        # expected scores then the SKLL model type must actually
        # support probabilistic classification. If it's not a SKLL
        # model at all, we just treat it as a LinearRegression model
        # which is basically what they all are in the end.
        if context == "rsmtool" and new_config["predict_expected_scores"]:
            model_name = new_config["model"]
            dummy_learner = (
                Learner(model_name) if is_skll_model(model_name) else Learner("LinearRegression")
            )
            if not hasattr(dummy_learner.model_type, "predict_proba"):
                raise ValueError(
                    f"{model_name} does not support expected scores "
                    f"since it is not a probablistic classifier."
                )
            del dummy_learner

        # 11. Raise a warning if we are specifiying a feature file but also
        # telling the system to automatically select transformations
        if new_config["features"] and new_config["select_transformations"]:
            # Show a warning unless a user passed a list of features.
            if not isinstance(new_config["features"], list):
                warnings.warn(
                    "You specified a feature file but also set "
                    "`select_transformations` to True. Any "
                    "transformations or signs specified in "
                    "the feature file will be overwritten by "
                    "the automatically selected transformations "
                    "and signs."
                )

        # 13. If we have `experiment_names`, check that the length of the list
        # matches the list of experiment_dirs.
        if context == "rsmsummarize" and new_config["experiment_names"]:
            if len(new_config["experiment_names"]) != len(new_config["experiment_dirs"]):
                raise ValueError(
                    "The number of specified experiment names should be the same"
                    " as the number of specified experiment directories."
                )

        # 14. Check that if the user specified min_n_per_group, they also
        # specified subgroups. If they supplied a dictionary, make
        # sure the keys match
        if new_config["min_n_per_group"]:
            # make sure we have subgroups
            if "subgroups" not in new_config:
                raise ValueError(
                    "You must specify a list of subgroups in "
                    "in the `subgroups` field if "
                    "you want to use the `min_n_per_group` field"
                )
            # if we got dictionary, make sure the keys match
            elif isinstance(new_config["min_n_per_group"], dict):
                if sorted(new_config["min_n_per_group"].keys()) != sorted(new_config["subgroups"]):
                    raise ValueError(
                        "The keys in `min_n_per_group` must "
                        "match the subgroups in `subgroups` field"
                    )
            # else convert to dictionary
            else:
                new_config["min_n_per_group"] = {
                    group: new_config["min_n_per_group"] for group in new_config["subgroups"]
                }

        # 15. Check that if the user enables logging to W&B, they also
        # specified wandb project and entity.
        if new_config["use_wandb"]:
            # make sure we have project name and entity
            if not new_config["wandb_project"] or not new_config["wandb_entity"]:
                raise ValueError(
                    "You must specify both `wandb_project` "
                    "and `wandb_entity` if you want to enable "
                    "logging to W&B."
                )

        # 16. Clean up config dict to keep only context-specific fields
        context_relevant_fields = (
            CHECK_FIELDS[context]["optional"] + CHECK_FIELDS[context]["required"]
        )

        new_config = {k: v for k, v in new_config.items() if k in context_relevant_fields}

        return new_config

    @classmethod
    def process_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the given configuration dictionary.

        Converts fields which are read in as string to the
        appropriate format. Fields which can take multiple
        string values are converted to lists if they have
        not been already formatted as such.

        Parameters
        ----------
        config : Dict[str, Any]
            Given Configuration dictionary to be processed.

        Returns
        -------
        new_config : Dict[str, Any]
            A copy of the given configuration dictionary with all
            fields converted to the appropriate format.

        Raises
        ------
        NameError
            If ``config`` does not exist, or ``config`` could not be read.
        ValueError
            If boolean configuration fields contain a value other then
            "true" or "false" (in JSON).
        """
        # Get the parameter dictionary
        new_config = deepcopy(config)

        # convert multiple values into lists
        for field in LIST_FIELDS:
            if field in new_config and new_config[field] is not None:
                if not isinstance(new_config[field], list):
                    new_config[field] = new_config[field].split(",")
                    new_config[field] = [prefix.strip() for prefix in new_config[field]]

        # make sure all boolean values are boolean
        for field in BOOLEAN_FIELDS:
            error_message = f"Field {field} can only be set to True or False."
            if field in new_config and new_config[field] is not None:
                if not isinstance(new_config[field], bool):
                    # we first convert the value to string to avoid
                    # attribute errors in case the user supplied an integer.
                    given_value = str(new_config[field]).strip()
                    m = re.match(r"^(true|false)$", given_value, re.I)
                    if not m:
                        raise ValueError(error_message)
                    else:
                        bool_value = json.loads(m.group().lower())
                        new_config[field] = bool_value

        return new_config

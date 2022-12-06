.. _usage_rsmsummarize:

``rsmsummarize`` - Compare multiple scoring models
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

RSMTool provides the ``rsmsummarize`` command-line utility to compare multiple models and to generate a comparison report. Unlike ``rsmcompare`` which creates a detailed comparison report between the two models, ``rsmsummarize`` can be used to create a more general overview of multiple models. 

``rsmsummarize`` can be used to compare:

1. Multiple ``rsmtool`` experiments, or
2. Multiple ``rsmeval`` experiments, or
3. A mix of ``rsmtool`` and ``rsmeval`` experiments (in this case, only the evaluation analyses will be compared).


.. note::

    It is strongly recommend that the original experiments as well as the summary experiment are all done using the same version of RSMTool.

.. include:: tutorial_rsmsummarize.rst.inc

Input
"""""

``rsmsummarize`` requires a single argument to run an experiment: the path to :ref:`a configuration file <config_file_rsmsummarize>`. You can specify which models you want to compare and the name of the report by supplying the path to :ref:`a configuration file <config_file_rsmsummarize>`. It can also take an output directory as an optional second argument. If the latter is not specified, ``rsmsummarize`` will use the current directory as the output directory.

Here are all the arguments to the ``rsmsummarize`` command-line script.

.. program:: rsmsummarize

.. option:: config_file 

    The :ref:`JSON configuration file <config_file_rsmsummarize>` for this experiment.

.. option:: output_dir (optional)

    The output directory where the report and intermediate ``.csv`` files for this comparison will be stored.

.. option:: -f, --force

    If specified, the contents of the output directory will be overwritten even if it already contains the output of another rsmsummarize experiment.

.. option:: -h, --help

    Show help message and exist.

.. option:: -V, --version

    Show version number and exit.

.. include:: config_rsmsummarize.rst.inc

.. _output_dirs_rsmsummarize:

Output
""""""

``rsmsummarize`` produces a set of folders in the output directory.

report
~~~~~~
This folder contains the final ``rsmsummarize`` report in HTML format as well as in the form of a Jupyter notebook (a ``.ipynb`` file).

output
~~~~~~
This folder contains all of the :ref:`intermediate files <intermediate_files_rsmsummarize>` produced as part of the various analyses performed, saved as ``.csv`` files. ``rsmsummarize`` will also save in this folder a copy of the :ref:`configuration file <config_file_rsmsummarize>`. Fields not specified in the original configuration file will be pre-populated with default values. 

figure
~~~~~~
This folder contains all of the figures that may be generated as part of the various analyses performed, saved as ``.svg`` files. Note that no figures are generated by the existing ``rsmsummarize`` notebooks. 

.. include:: intermediate_files_rsmsummarize.rst.inc
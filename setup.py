from __future__ import print_function
import os
from os.path import join as pjoin
import sys, subprocess

requires = ['progressbar2', 'mpi4py', 'numpy', 'cython', 'scipy', 'matplotlib', 'h5py', 'colorama',
            'psutil']

if '--nocuda' in sys.argv:
  sys.argv.remove('--nocuda')
  HAVE_CUDA = False
else:
  try:
    subprocess.check_call(['nvcc', '--version'])
    requires += ['cudamat==0.3circus']
    HAVE_CUDA = True
  except (OSError, subprocess.CalledProcessError):
    print("CUDA not found")
    HAVE_CUDA = False

from setuptools import setup
from setuptools.command.install import install

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

if sys.version_info < (2, 7):
    raise RuntimeError('Only Python versions >= 2.7 are supported')

if 'CONDA_BUILD' in os.environ and 'RECIPE_DIR' in os.environ:
    # We seem to be running under a "conda build"
    data_path = pjoin('data', 'spyking-circus')
else:
    data_path = pjoin(os.path.expanduser('~'), 'spyking-circus')

setup(name='spyking-circus',
      version='0.4.3',
      description='Fast spike sorting by template matching',
      long_description=read('README.rst'),
      url='http://spyking-circus.rtfd.org',
      author='Pierre Yger and Olivier Marre',
      author_email='pierre.yger@inserm.fr',
      license='License :: OSI Approved :: UPMC CNRS INSERM Logiciel Libre License, version 2.1 (CeCILL-2.1)',
      keywords="spike sorting template matching tetrodes extracellular",
      packages=['circus', 'circus.shared', 'circus.scripts'],
      setup_requires=['cython', 'numpy', 'setuptools>0.18'],
      dependency_links=["https://github.com/yger/cudamat/archive/master.zip#egg=cudamat-0.3circus"],
      install_requires=requires,
      entry_points={
          'console_scripts': [
              'spyking-circus=circus.scripts.launch:main',
              'spyking-circus-subtask=circus.scripts.subtask:main',
              'circus-multi=circus.scripts.circus_multi:main',
              'circus-gui-matlab=circus.scripts.matlab_gui:main',
              'circus-gui-python=circus.scripts.python_gui:main'
          ],
          'gui_scripts': [
              'spyking-circus-launcher=circus.scripts.launch_gui:main'
          ]
      },
      extras_require={'beer': ['scikit-learn']},
      package_data={'circus': ['config.params',
                               # Only include the actual GUI, not other test scripts
                               pjoin('matlab_GUI', 'SortingGUI.m'),
                               pjoin('matlab_GUI', 'SortingGUI.fig'),
                               pjoin('matlab_GUI', 'strjoin.m'),
                               pjoin('matlab_GUI', 'strsplit.m'),
                               pjoin('matlab_GUI', 'DATA_SortingGUI.m'),
                               pjoin('matlab_GUI', 'xcorr.m'),
                               pjoin('icons', 'gimp-tool-color-picker.png'),
                               pjoin('icons', 'gimp-tool-free-select.png'),
                               pjoin('icons', 'logo.jpg'),
                               pjoin('icons', 'icon.png'),
                               pjoin('icons', 'gimp-tool-rect-select.png'),
                               pjoin('qt_GUI', 'qt_merge.ui'),
                               pjoin('qt_GUI', 'qt_preview.ui'),
                               pjoin('qt_GUI', 'qt_launcher.ui')]},                               
      data_files=[(data_path, [pjoin('circus', 'config.params')]),
                  (pjoin(data_path, 'probes'), [pjoin('probes', 'mea_64.prb')]),
                  (pjoin(data_path, 'probes'), [pjoin('probes', 'mea_252.prb')]),
                  (pjoin(data_path, 'probes'), [pjoin('probes', 'small_mea_252.prb')]),
                  (pjoin(data_path, 'probes'), [pjoin('probes', 'wide_mea_252.prb')]),
                  (pjoin(data_path, 'probes'), [pjoin('probes', 'imec.prb')]),
                  (pjoin(data_path, 'probes'), [pjoin('probes', 'kampff_32.prb')]),
                  (pjoin(data_path, 'probes'), [pjoin('probes', 'kampff_128.prb')]),
                  (pjoin(data_path, 'probes'), [pjoin('probes', 'mea_4225.prb')])],
      use_2to3=True,
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Science/Research',
          'License :: Other/Proprietary License',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 3',
          'Topic :: Scientific/Engineering :: Bio-Informatics'
      ],
      zip_safe=False)

msg = ['################################################################################',
'# Probes files and parameter template have been copied to $HOME/spyking-circus #']


if HAVE_CUDA:
  msg += ['# GPU support has been correctly installed                                     #']
else:
  msg += ['# GPU support was NOT installed. Be sure to have a valid nvcc command          #']

msg += ['################################################################################']

for line in msg:
  print(line)

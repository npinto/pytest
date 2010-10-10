import os, sys
if sys.version_info >= (3,0):
    from distribute_setup import use_setuptools
    use_setuptools()
from setuptools import setup

long_description = """
cross-project testing tool with many advanced features

Platforms: Linux, Win32, OSX

Interpreters: Python versions 2.4 through to 3.2, Jython 2.5.1 and PyPy

Bugs and issues: http://bitbucket.org/hpk42/py-trunk/issues/

Mailing lists and more contact points: http://pylib.org/contact.html

.. _`py.test`: http://pytest.org
.. _`py.path`: http://pylib.org/path.html
.. _`py.code`: http://pylib.org/code.html

(c) Holger Krekel and others, 2004-2010
"""
def main():
    setup(
        name='pytest',
        description='py.test: simple testing with Python',
        long_description = long_description,
        version= '2.0.0.dev0',
        url='http://pylib.org',
        license='MIT license',
        platforms=['unix', 'linux', 'osx', 'cygwin', 'win32'],
        author='holger krekel, Guido Wesdorp, Carl Friedrich Bolz, Armin Rigo, Maciej Fijalkowski & others',
        author_email='holger at merlinux.eu',
        entry_points= make_entry_points(),
        install_requires=['pylib>=1.9.9'],
        classifiers=['Development Status :: 6 - Mature',
                     'Intended Audience :: Developers',
                     'License :: OSI Approved :: MIT License',
                     'Operating System :: POSIX',
                     'Operating System :: Microsoft :: Windows',
                     'Operating System :: MacOS :: MacOS X',
                     'Topic :: Software Development :: Testing',
                     'Topic :: Software Development :: Libraries',
                     'Topic :: Utilities',
                     'Programming Language :: Python',
                     'Programming Language :: Python :: 3'],
        packages=['pytest', 'pytest.plugin', ],
        zip_safe=False,
    )

def cmdline_entrypoints(versioninfo, platform, basename):
    target = 'pytest:__main__'
    if platform.startswith('java'):
        points = {'py.test-jython': target}
    else:
        if basename.startswith("pypy"):
            points = {'py.test-%s' % basename: target}
        else: # cpython
            points = {'py.test-%s.%s' % versioninfo[:2] : target,}
        points['py.test'] = target
    return points

def make_entry_points():
    basename = os.path.basename(sys.executable)
    points = cmdline_entrypoints(sys.version_info, sys.platform, basename)
    keys = list(points.keys())
    keys.sort()
    l = ["%s = %s" % (x, points[x]) for x in keys]
    return {'console_scripts': l}

if __name__ == '__main__':
    main()


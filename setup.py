"""py2app build-script voor CalcMacApp.

Op macOS in een venv:
    pip install py2app
    python3 setup.py py2app

Resultaat: dist/CalcMacApp.app — kan je naar /Applications slepen.
.c4y bestanden zijn na installatie te koppelen via Finder → 'Open With'.
"""

from setuptools import setup

APP = ['runapp.py']

# UTI + documenttype-declaratie. Hierdoor weet macOS dat .c4y een file-type
# is dat door deze app geopend kan worden.
PLIST = {
    'CFBundleName':            'CalcMacApp',
    'CFBundleDisplayName':     'CalcMacApp',
    'CFBundleIdentifier':      'nl.bashania.calcmacapp',
    'CFBundleVersion':         '0.1.0',
    'CFBundleShortVersionString': '0.1.0',
    'NSHighResolutionCapable': True,
    'CFBundleDocumentTypes': [{
        'CFBundleTypeName':       'Calc4You-begroting',
        'CFBundleTypeRole':       'Editor',
        'LSHandlerRank':          'Owner',
        'CFBundleTypeExtensions': ['c4y'],
        'LSItemContentTypes':     ['nl.bashania.calc4you'],
    }],
    'UTExportedTypeDeclarations': [{
        'UTTypeIdentifier':  'nl.bashania.calc4you',
        'UTTypeDescription': 'Calc4You-begrotingsbestand',
        'UTTypeConformsTo':  ['public.xml'],
        'UTTypeTagSpecification': {
            'public.filename-extension': ['c4y'],
            'public.mime-type':          ['application/xml'],
        },
    }],
}

import os as _os

_ICONFILE = _os.path.join('app', 'icons', 'app_icon.icns')

OPTIONS = {
    'argv_emulation': False,    # we vangen FileOpen-events zelf op
    'plist':          PLIST,
    'packages':       ['PyQt6'],
    'includes':       [
        'app',
        'app.c4y_io', 'app.calc', 'app.commands', 'app.validations',
        'app.main',   'app.find_bar',
    ],
    # Sluit de iconen-map en validations-module mee in de bundel
    'resources': ['app/icons'] if _os.path.isdir('app/icons') else [],
}
if _os.path.exists(_ICONFILE):
    OPTIONS['iconfile'] = _ICONFILE

setup(
    app=APP,
    name='CalcMacApp',
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

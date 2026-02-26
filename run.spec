# CM_Loans.spec
# ------------------------------------------
import os  # ✅ Move this to the top

block_cipher = None

datas = [
    (os.path.abspath('LoanMVP/templates'), 'LoanMVP/templates'),
    (os.path.abspath('LoanMVP/static'), 'LoanMVP/static'),
    (os.path.abspath('LoanMVP/instance'), 'LoanMVP/instance'),
]

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,  # ✅ Use the variable here
    hiddenimports=[
        'openai', 'flask_wtf', 'flask_socketio', 'engineio.async_drivers.threading',
        'eventlet', 'python_dotenv', 'twilio', 'twilio.rest', 'sendgrid', 'flask_mail'
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CM Loans',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name='CM Loans'
)
; ==========================================
; Caughman Mason LoanMVP / CM Loans Installer
; ==========================================

[Setup]
AppName=Caughman Mason LoanMVP
AppVersion=1.0
AppPublisher=Caughman Mason LLC
AppPublisherURL=https://www.caughmanmason.com
DefaultDirName={pf}\Caughman Mason\LoanMVP
DefaultGroupName=Caughman Mason
UninstallDisplayIcon={app}\CM Loans.exe
OutputDir={src}
OutputBaseFilename=CM_Loans_Installer
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
SetupLogging=yes

[Files]
Source: ".\dist\CM Loans.exe"; DestDir: "{app}"; Flags: ignoreversion
; Optional: include config/log folders if you want
Source: ".\logs\*"; DestDir: "{app}\logs"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CM Loans"; Filename: "{app}\CM Loans.exe"
Name: "{commondesktop}\CM Loans"; Filename: "{app}\CM Loans.exe"
Name: "{group}\Uninstall CM Loans"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\CM Loans.exe"; Description: "Launch CM Loans"; Flags: nowait postinstall skipifsilent


[UninstallRun]
; Stop the CM Loans service (silent and safe)
Filename: "{app}\nssm.exe"; Parameters: "stop ""CM Loans"""; Flags: waituntilterminated skipifdoesntexist

; Remove the CM Loans service
Filename: "{app}\nssm.exe"; Parameters: "remove ""CM Loans"" confirm"; Flags: waituntilterminated skipifdoesntexist

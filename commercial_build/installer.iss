; =============================================================================
; Inno Setup Script: AI Attribute Wrangle Commercial Installer
; Compiles into a single, standalone Setup_AI_Attribute_Wrangle.exe
; =============================================================================

#define MyAppName "AI Attribute Wrangle"
#define MyAppVersion "1.0.3"
#define MyAppPublisher "Procedural AI Systems"
#define MyAppURL "https://github.com/ai-attribute-wrangle"
#define MyAppExeName "Setup.exe"

[Setup]
AppId={{E58421A1-8899-4A1B-9988-1234567890AB}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\AI_Attribute_Wrangle
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=Setup_AI_Attribute_Wrangle_v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\otls\ai_attribwrangle.hda

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Distributable payload
Source: "..\dist\AI_Attribute_Wrangle_v1.0.2\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Setup & License Manager"; Filename: "pythonw.exe"; Parameters: """{app}\installer_gui.py"""
Name: "{group}\Documentation"; Filename: "{app}\README.txt"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Code]
// Automatically discover Houdini preference folders and write packages/ai_attribwrangle.json
procedure CurStepChanged(CurStep: TSetupStep);
var
  DocsDir, HoudiniDir, PackagesDir, JsonPath, Content, AppDirFwd: string;
  FindRec: TFindRec;
begin
  if CurStep = ssPostInstall then
  begin
    DocsDir := ExpandConstant('{userdocs}');
    AppDirFwd := ExpandConstant('{app}');
    StringChange(AppDirFwd, '\', '/');
    
    Content := '{'#13#10 +
               '  "hpath": "' + AppDirFwd + '",'#13#10 +
               '  "env": ['#13#10 +
               '    { "PYTHONPATH": "' + AppDirFwd + '/python;$PYTHONPATH" },'#13#10 +
               '    { "PATH": "' + AppDirFwd + '/bin;$PATH" },'#13#10 +
               '    { "AI_WRANGLE_ROOT": "' + AppDirFwd + '" }'#13#10 +
               '  ]'#13#10 +
               '}';

    if FindFirst(DocsDir + '\houdini*', FindRec) then
    begin
      try
        repeat
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0) and (FindRec.Name <> '.') and (FindRec.Name <> '..') then
          begin
            HoudiniDir := DocsDir + '\' + FindRec.Name;
            PackagesDir := HoudiniDir + '\packages';
            ForceDirectories(PackagesDir);
            JsonPath := PackagesDir + '\ai_attribwrangle.json';
            SaveStringToFile(JsonPath, Content, False);
          end;
        until not FindNext(FindRec);
      finally
        FindClose(FindRec);
      end;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DocsDir, HoudiniDir, JsonPath: string;
  FindRec: TFindRec;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DocsDir := ExpandConstant('{userdocs}');
    if FindFirst(DocsDir + '\houdini*', FindRec) then
    begin
      try
        repeat
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0) then
          begin
            HoudiniDir := DocsDir + '\' + FindRec.Name;
            JsonPath := HoudiniDir + '\packages\ai_attribwrangle.json';
            if FileExists(JsonPath) then
              DeleteFile(JsonPath);
          end;
        until not FindNext(FindRec);
      finally
        FindClose(FindRec);
      end;
    end;
  end;
end;

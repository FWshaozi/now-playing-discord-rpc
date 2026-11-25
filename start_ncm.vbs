' Silent launcher for ncm_rpc.py (Discord Rich Presence bridge)
' Double-click to start with no console window. Logs are written by the script
' itself into .\logs\ncm_rpc-YYYYMMDD.log when running without a console.

Option Explicit

Const START_DELAY_MS = 20000   ' wait 20s for Discord / Now Playing to come up
Const SCRIPT_NAME = "ncm_rpc.py"

Dim sh, fso, baseDir, scriptPath, pyw

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = fso.BuildPath(baseDir, SCRIPT_NAME)

If Not fso.FileExists(scriptPath) Then
    MsgBox SCRIPT_NAME & " not found in:" & vbCrLf & baseDir, vbCritical, "Launch failed"
    WScript.Quit 1
End If

If AlreadyRunning() Then
    MsgBox "The bridge is already running." & vbCrLf & vbCrLf & _
           "Use stop_ncm.cmd to stop it first if you want to restart.", _
           vbInformation, "Already running"
    WScript.Quit 0
End If

pyw = FindPythonW(sh, fso)

If START_DELAY_MS > 0 Then WScript.Sleep START_DELAY_MS

sh.CurrentDirectory = baseDir
sh.Run """" & pyw & """ """ & scriptPath & """", 0, False

' True if a python/pythonw process is already running this exact script.
Function AlreadyRunning()
    Dim wmi, procs, proc
    AlreadyRunning = False
    On Error Resume Next
    Set wmi = GetObject("winmgmts:\\.\root\cimv2")
    If Err.Number <> 0 Then
        Err.Clear
        Exit Function
    End If
    Set procs = wmi.ExecQuery("SELECT ProcessId, CommandLine FROM Win32_Process WHERE Name='pythonw.exe' OR Name='python.exe'")
    For Each proc In procs
        If Not IsNull(proc.CommandLine) Then
            If InStr(1, proc.CommandLine, SCRIPT_NAME, vbTextCompare) > 0 Then
                AlreadyRunning = True
                Exit Function
            End If
        End If
    Next
End Function

' Locate pythonw.exe: real install first, then WindowsApps alias, then pyw launcher.
Function FindPythonW(sh, fso)
    Dim folder, subFolder, candidate

    candidate = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Python\pythoncore-3.15-64\pythonw.exe")
    If fso.FileExists(candidate) Then
        FindPythonW = candidate
        Exit Function
    End If

    folder = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Python")
    If fso.FolderExists(folder) Then
        For Each subFolder In fso.GetFolder(folder).SubFolders
            If LCase(Left(subFolder.Name, 10)) = "pythoncore" Then
                candidate = fso.BuildPath(subFolder.Path, "pythonw.exe")
                If fso.FileExists(candidate) Then
                    FindPythonW = candidate
                    Exit Function
                End If
            End If
        Next
    End If

    candidate = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe")
    If fso.FileExists(candidate) Then
        FindPythonW = candidate
        Exit Function
    End If

    FindPythonW = "pyw.exe"
End Function

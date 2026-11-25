' Install autostart: adds a shortcut to the current user's Startup folder.
' No administrator rights required. Double-click to install.
Option Explicit

Dim sh, fso, baseDir, launcher, startupDir, lnkPath, lnk

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = fso.BuildPath(baseDir, "start_ncm.vbs")

If Not fso.FileExists(launcher) Then
    MsgBox "start_ncm.vbs not found in:" & vbCrLf & baseDir, vbCritical, "Install failed"
    WScript.Quit 1
End If

startupDir = sh.SpecialFolders("Startup")
lnkPath = fso.BuildPath(startupDir, "Now Playing Discord RPC.lnk")

Set lnk = sh.CreateShortcut(lnkPath)
lnk.TargetPath = sh.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\wscript.exe"
lnk.Arguments = """" & launcher & """"
lnk.WorkingDirectory = baseDir
lnk.WindowStyle = 7
lnk.Description = "Now Playing -> Discord Rich Presence"
lnk.Save

If fso.FileExists(lnkPath) Then
    MsgBox "Autostart installed successfully:" & vbCrLf & lnkPath & vbCrLf & vbCrLf & _
           "The bridge will start ~20s after logon.", vbInformation, "Done"
Else
    MsgBox "Failed to create the shortcut.", vbCritical, "Error"
    WScript.Quit 1
End If

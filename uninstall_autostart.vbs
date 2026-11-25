' Remove autostart: deletes the Startup folder shortcut created by install_autostart.vbs.
Option Explicit

Dim sh, fso, startupDir, lnkPath

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

startupDir = sh.SpecialFolders("Startup")
lnkPath = fso.BuildPath(startupDir, "Now Playing Discord RPC.lnk")

If fso.FileExists(lnkPath) Then
    fso.DeleteFile lnkPath, True
    MsgBox "Autostart removed." & vbCrLf & lnkPath, vbInformation, "Done"
Else
    MsgBox "Autostart shortcut not found:" & vbCrLf & lnkPath, vbInformation, "Nothing to do"
End If

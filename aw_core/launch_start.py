import os
import subprocess
import sys
import plistlib

if sys.platform == "win32":
    import winshell

if sys.platform == "win32":
    startup_path = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
    shortcut_name = 'TTim.lnk'
    file_path = os.path.abspath(__file__)
    _module_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    app_path = os.path.join(_module_dir, 'aw-qt.exe')
if sys.platform == "darwin":
    app_path = "/Applications/TTim.app"
    app_name = "TTim"


def launch_app():
    cmd = f"osascript -e 'tell application \"System Events\" to make login item at end with properties {{path:\"{app_path}\", hidden:false}}'"
    subprocess.run(cmd, shell=True)


def delete_launch_app():
    cmd = f"osascript -e 'tell application \"System Events\" to delete login item \"{app_name}\"'"
    subprocess.run(cmd, shell=True)


def get_login_items():
    data = []
    cmd = "osascript -e 'tell application \"System Events\" to get the name of every login item'"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    data = result.stdout.strip().split(", ")
    if "TTim" in data:
        return True
    return False


def check_startup_status():
    if sys.platform == "darwin":
        return get_login_items()
    elif sys.platform == "win32":
        shortcut = os.path.join(startup_path, shortcut_name)
        if os.path.exists(shortcut):
            return True, 200
        else:
            return False, 200


# Windows

def create_shortcut():
    print(app_path)
    shortcut = os.path.join(startup_path, shortcut_name)
    with winshell.shortcut(shortcut) as link:
        link.path = app_path
        link.description = "Shortcut for YourApp"
    return {"status": "success", "message": "Shortcut created successfully"}


def delete_shortcut():
    shortcut = os.path.join(startup_path, shortcut_name)
    if os.path.exists(shortcut):
        os.remove(shortcut)
        return {"status": "success", "message": "Shortcut deleted successfully"}
    else:
        return {"status": "error", "message": "Shortcut not found"}

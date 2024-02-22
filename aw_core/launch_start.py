import os
import subprocess
import sys
import plistlib
if sys.platform == "win32":
    import winshell

if sys.platform == "win32":
    startup_path = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
    shortcut_name = 'Sundial.lnk'
    file_path = os.path.abspath(__file__)
    _module_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    app_path = os.path.join(_module_dir, 'aw-qt.exe')



# Mac
def load_plist(plist_path):
    # Load and start the service using launchctl
    os.system(f"launchctl load {plist_path}")
    os.system(f"launchctl start com.ralvie.sundial")
def launch_app():
    plist_content = {
        'Label': 'com.ralvie.sundial',
        'ProgramArguments': ['/Applications/Sundial.app/Contents/MacOS/aw-qt'],
        'RunAtLoad': True,
        # Add other keys and values as needed
    }

    # Define the path to the LaunchAgents directory and the plist file
    launchagents_dir = os.path.expanduser('~/Library/LaunchAgents')
    plist_path = os.path.join(launchagents_dir, 'com.ralvie.sundial.plist')

    # Write the plist content to the file
    with open(plist_path, 'wb') as plist_file:
        plistlib.dump(plist_content, plist_file)

    print(f"Created plist file: {plist_path}")

def delete_launch_app():
    plist_path = os.path.expanduser('~/Library/LaunchAgents/com.ralvie.sundial.plist')

    # Check if the plist file exists before attempting to delete it
    if os.path.exists(plist_path):
        os.remove(plist_path)
        print("Deleted plist file.")
    else:
        print("Plist file does not exist.")

def check_startup_status():
    if sys.platform == "darwin":
        bundle_identifier = "net.ralvie.Sundial"
        command = f"launchctl list | grep {bundle_identifier}"
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if result.returncode == 0:
            print(f"The application with bundle identifier '{bundle_identifier}' starts on launch.")
            return True
        else:
            print(f"The application with bundle identifier '{bundle_identifier}' does not start on launch.")
            return False
    elif sys.platform == "win32":
        shortcut = os.path.join(startup_path, shortcut_name)
        if os.path.exists(shortcut):
            return {"status": "enabled"}, 200
        else:
            return {"status": "disabled"}, 200
    

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

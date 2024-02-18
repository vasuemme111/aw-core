import os
import getpass
import subprocess
import sys
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
    plist_content = f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST  1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>net.ralvie.Sundial</string>
            <key>ProgramArguments</key>
            <array>
                <string>/Applications/Sundial.app/Contents/MacOS/aw-qt</string>
            </array>
            <key>RunAtLoad</key>
            <true/>
            <key>Description</key>
            <string>Sundial</string>
        </dict>
        </plist>
        """

    # Get the current user's username
    username = getpass.getuser()

    # Define the path to the user's LaunchAgents directory
    plist_dir = f"/Users/{username}/Library/LaunchAgents/"

    # Ensure the directory exists, if not, create it
    os.makedirs(plist_dir, exist_ok=True)

    # Define the path to save the plist file
    plist_path = os.path.join(plist_dir, "com.ralvie.sundial.plist")

    # Write the plist content to the file
    with open(plist_path, "w") as plist_file:
        plist_file.write(plist_content)
    load_plist(plist_path)
    return True

def delete_launch_app():
    username = getpass.getuser()
    plist_dir = f"/Users/{username}/Library/LaunchAgents/"

    # Ensure the directory exists, if not, create it
    os.makedirs(plist_dir, exist_ok=True)

    # Define the path to save the plist file
    plist_path = os.path.join(plist_dir, "com.ralvie.sundial.plist")
    # Unload and delete the service using launchctl
    os.system(f"launchctl unload {plist_path}")
    os.remove(plist_path)
    return True

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

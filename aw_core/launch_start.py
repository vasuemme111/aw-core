import os
import subprocess
import sys
import plistlib
if sys.platform == "win32":
    import winreg

if sys.platform == "win32":
    file_path = os.path.abspath(__file__)
    _module_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    app_path = os.path.join(_module_dir, 'aw-qt.exe')


def is_plist_in_launch_agents():
    plist_filename = "com.ralvie.TTim.plist"
    launch_agents_path = os.path.expanduser("~/Library/LaunchAgents")
    plist_path = os.path.join(launch_agents_path, plist_filename)
    return os.path.isfile(plist_path)

# Mac
def load_plist(plist_path):
    # Load and start the service using launchctl
    os.system(f"launchctl load {plist_path}")

def launch_app():
    plist_content = {
        'Label': 'com.ralvie.TTim',
        'ProgramArguments': ['/Applications/TTim.app/Contents/MacOS/aw-qt'],
        'RunAtLoad': True,
        # Add other keys and values as needed
    }

    # Define the path to the LaunchAgents directory and the plist file
    launchagents_dir = os.path.expanduser('~/Library/LaunchAgents')
    plist_path = os.path.join(launchagents_dir, 'com.ralvie.TTim.plist')

    # Write the plist content to the file
    with open(plist_path, 'wb') as plist_file:
        plistlib.dump(plist_content, plist_file)
    print(f"Created plist file: {plist_path}")

def delete_launch_app():
    plist_path = os.path.expanduser('~/Library/LaunchAgents/com.ralvie.TTim.plist')

    # Check if the plist file exists before attempting to delete it
    if os.path.exists(plist_path):
        os.system(f"launchctl stop com.ralvie.TTim")
        os.system(f"launchctl unload {plist_path}")
        os.remove(plist_path)
        os.system(f"launchctl load {plist_path}")
        print("Deleted plist file.")
    else:
        print("Plist file does not exist.")

def check_startup_status():
    if sys.platform == "darwin":
        bundle_identifier = "net.ralvie.TTim"
        command = f"launchctl list | grep {bundle_identifier}"
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if result.returncode == 0 or is_plist_in_launch_agents():
            print(f"The application with bundle identifier '{bundle_identifier}' starts on launch.")
            return True
        else:
            print(f"The application with bundle identifier '{bundle_identifier}' does not start on launch.")
            return False
    elif sys.platform == "win32":
            key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
            with winreg.OpenKey(
                    key=winreg.HKEY_CURRENT_USER,
                    sub_key=key_path,
                    reserved=0,
                    access=winreg.KEY_READ,
            ) as key:
                try:
                    value, _ = winreg.QueryValueEx(key, "TTim")
                    return True
                except FileNotFoundError:
                    return False
    

# Windows

def set_autostart_registry(autostart: bool = True) -> bool:
    """
    Create/update/delete Windows autostart registry key

    :param app_name:    A string containing the name of the application
    :param app_path:    A string specifying the application path
    :param autostart:   True - create/update autostart key / False - delete autostart key
    :return:            True - Success / False - Error, app name doesn't exist
    """
    key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
    with winreg.OpenKey(
            key=winreg.HKEY_CURRENT_USER,
            sub_key=key_path,
            reserved=0,
            access=winreg.KEY_ALL_ACCESS,
    ) as key:
        try:
            if autostart:
                winreg.SetValueEx(key, "TTim", 0, winreg.REG_SZ, app_path)
            else:
                winreg.DeleteValue(key, "TTim")
        except OSError:
            return False
    return True



import os
import getpass
import subprocess


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
    bundle_identifier = "net.ralvie.sundial"
    command = f"launchctl list | grep {bundle_identifier}"
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if result.returncode == 0:
        print(f"The application with bundle identifier '{bundle_identifier}' starts on launch.")
        return True
    else:
        print(f"The application with bundle identifier '{bundle_identifier}' does not start on launch.")
        return False
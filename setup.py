import os
import sys
import subprocess
import winreg
import shutil
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    required_version = (3, 8)
    current_version = sys.version_info[:2]
    
    if current_version < required_version:
        print(f"Error: Python {required_version[0]}.{required_version[1]} or higher is required.")
        print(f"Current version: {current_version[0]}.{current_version[1]}")
        return False
    return True

def install_requirements():
    """Install required packages"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        return True
    except subprocess.CalledProcessError:
        print("Error: Failed to install requirements")
        return False

def create_config_file():
    """Create .env file for API key"""
    env_path = Path(".env")
    if not env_path.exists():
        with open(env_path, "w") as f:
            f.write("# Google API Key Configuration\n")
            f.write("GOOGLE_API_KEY=your_api_key_here\n")
        print("Created .env file. Please edit it to add your Google API key.")

def create_desktop_shortcut():
    """Create a desktop shortcut to run the application"""
    try:
        desktop = Path(os.path.expanduser("~/Desktop"))
        shortcut_path = desktop / "QuoteFlow.lnk"
        
        # Get the path to the current directory
        current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        run_app_path = current_dir / "run_app.bat"
        
        # Create the shortcut using PowerShell
        ps_script = f"""
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
        $Shortcut.TargetPath = "{run_app_path}"
        $Shortcut.WorkingDirectory = "{current_dir}"
        $Shortcut.Description = "QuoteFlow Document Assistant"
        $Shortcut.Save()
        """
        
        subprocess.run(["powershell", "-Command", ps_script], check=True)
        print(f"Created desktop shortcut at: {shortcut_path}")
        return True
    except Exception as e:
        print(f"Error creating shortcut: {e}")
        return False

def main():
    print("QuoteFlow Setup")
    print("==============")
    
    if not check_python_version():
        input("Press Enter to exit...")
        return
    
    print("\nInstalling required packages...")
    if not install_requirements():
        input("Press Enter to exit...")
        return
    
    print("\nCreating configuration file...")
    create_config_file()
    
    print("\nCreating desktop shortcut...")
    create_desktop_shortcut()
    
    print("\nSetup complete!")
    print("1. Edit the .env file to add your Google API key")
    print("2. Use the desktop shortcut to run the application")
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main() 
"""
 python-pacman - (c) Jacob Cook 2015
 Licensed under GPLv3
"""

import subprocess, os, shutil, requests
from shlex import quote


__PACMAN_BIN = shutil.which("pacman")   # default to use the system's pacman binary


def get_bin():
    '''
    Return the current pacman binary being used.
    '''
    return __PACMAN_BIN


def set_bin(path):
    '''
    Set a custom pacman binary. 
    If the pacman binary is set to an AUR helper, this module may also be used to interact with AUR.
    '''
    global __PACMAN_BIN
    if isinstance(path, str) and (os.path.isfile(path) or os.path.isfile(shutil.which(path))):
        __PACMAN_BIN = shutil.which(path)
    else:
        raise IOError("This executable does not exist.")


def install(packages, needed=True):
    # Install package(s)
    s = pacman("-S", packages, ["--needed" if needed else None])
    if s["code"] != 0:
        raise Exception("Failed to install: {0}".format(s["stderr"]))


def refresh():
    # Refresh the local package information database
    s = pacman("-Sy")
    if s["code"] != 0:
        raise Exception("Failed to refresh database: {0}".format(s["stderr"]))


def upgrade(packages=[]):
    # Upgrade packages; if unspecified upgrade all packages
    if packages:
        install(packages)
    else:
        s = pacman("-Su")
    if s["code"] != 0:
        raise Exception("Failed to upgrade packages: {0}".format(s["stderr"]))


def remove(packages, purge=False):
    # Remove package(s), purge its files if requested
    s = pacman("-Rc{0}".format("n" if purge else ""), packages)
    if s["code"] != 0:
        raise Exception("Failed to remove: {0}".format(s["stderr"]))


def get_all():
    # List all packages, installed and not installed
    interim, results = {}, []
    s = pacman("-Q")
    if s["code"] != 0:
        raise Exception(
            "Failed to get installed list: {0}".format(s["stderr"])
        )
    for x in s["stdout"].split('\n'):
        if not x.split():
            continue
        x = x.split(' ')
        interim[x[0]] = {
            "id": x[0], "version": x[1], "upgradable": False,
            "installed": True
        }
    s = pacman("-Sl")
    if s["code"] != 0:
        raise Exception(
            "Failed to get available list: {0}".format(s["stderr"])
        )
    for x in s["stdout"].split('\n'):
        if not x.split():
            continue
        x = x.split(' ')
        if x[1] in interim:
            interim[x[1]]["repo"] = x[0]
            if interim[x[1]]["version"] != x[2]:
                interim[x[1]]["upgradable"] = x[2]
        else:
            results.append({
                "id": x[1], "repo": x[0], "version": x[2], "upgradable": False,
                "installed": False
            })
    for x in interim:
        results.append(interim[x])
    return results


def get_installed():
    # List all installed packages
    interim = {}
    s = pacman("-Q")
    if s["code"] != 0:
        raise Exception(
            "Failed to get installed list: {0}".format(s["stderr"])
        )
    for x in s["stdout"].split('\n'):
        if not x.split():
            continue
        x = x.split(' ')
        interim[x[0]] = {
            "id": x[0], "version": x[1], "upgradable": False,
            "installed": True
        }
    s = pacman("-Qu")
    if s["code"] != 0 and s["stderr"]:
        raise Exception(
            "Failed to get upgradable list: {0}".format(s["stderr"])
        )
    for x in s["stdout"].split('\n'):
        if not x.split():
            continue
        x = x.split(' -> ')
        name = x[0].split(' ')[0]
        if name in interim:
            r = interim[name]
            r["upgradable"] = x[1]
            interim[name] = r
    results = []
    for x in interim:
        results.append(interim[x])
    return results


def get_available():
    # List all available packages
    results = []
    s = pacman("-Sl")
    if s["code"] != 0:
        raise Exception(
            "Failed to get available list: {0}".format(s["stderr"])
        )
    for x in s["stdout"].split('\n'):
        if not x.split():
            continue
        x = x.split(' ')
        results.append({"id": x[1], "repo": x[0], "version": x[2]})
    return results


def get_info(package, pacman_bin=__PACMAN_BIN):
    # Get package information from database
    interim = []
    s = pacman("-Qi" if is_installed(package) else "-Si", package, pacman_bin=pacman_bin)
    if s["code"] != 0:
        raise Exception("Failed to get info: {0}".format(s["stderr"]))
    for x in s["stdout"].split('\n'):
        if not x.split():
            continue
        if ':' in x:
            x = x.split(':', 1)
            interim.append((x[0].strip(), x[1].strip()))
        else:
            data = interim[-1]
            data = (data[0], data[1] + "  " + x.strip())
            interim[-1] = data
    result = {}
    for x in interim:
        result[x[0]] = x[1]
    return result


def needs_for(packages):
    # Get list of not-yet-installed dependencies of these packages
    s = pacman("-Sp", packages, ["--print-format", "%n"])
    if s["code"] != 0:
        raise Exception("Failed to get requirements: {0}".format(s["stderr"]))
    return [x for x in s["stdout"].split('\n') if x]


def depends_for(packages):
    # Get list of installed packages that depend on these
    s = pacman("-Rpc", packages, ["--print-format", "%n"])
    if s["code"] != 0:
        raise Exception("Failed to get depends: {0}".format(s["stderr"]))
    return [x for x in s["stdout"].split('\n') if x]


def is_installed(package):
    # Return True if the specified package is installed
    return pacman("-Q", package)["code"] == 0


def is_aur(package):
    '''
    Return True if the given package is an AUR package.
    '''
    try:
        # search in official pacman repo
        matched_packages = pacman('-Ssq', package, pacman_bin="pacman").get('stdout').split('\n')
        for i in matched_packages:
            if i == package:
                # find a match in official repo. not aur.
                return False

        response = requests.request(method='post', url="https://aur.archlinux.org/packages/?O=0&SeB=N&K={}&outdated=&SB=n&SO=a&PP=50&do_Search=Go".format(package))
        if "No packages matched your search criteria." in response.text:
            return False
        return True

    except Exception as e:
        return False


def pacman(flags, pkgs=[], eflgs=[], pacman_bin=__PACMAN_BIN):
    # Subprocess wrapper, get all data
    if not pkgs:
        cmd = [pacman_bin, "--noconfirm", flags]
    elif type(pkgs) == list:
        cmd = [pacman_bin, "--noconfirm", flags]
        cmd += [quote(s) for s in pkgs]
    else:
        cmd = [pacman_bin, "--noconfirm", flags, pkgs]
    if eflgs and any(eflgs):
        eflgs = [x for x in eflgs if x]
        cmd += eflgs
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    data = p.communicate()
    data = {"code": p.returncode, "stdout": data[0].decode(),
            "stderr": data[1].rstrip(b'\n').decode()}
    return data

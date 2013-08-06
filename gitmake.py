import argparse
import time
import json
import os
import subprocess
import re

VERSION_FILENAME = 'version.json'
SETTINGS_FILENAME = 'gitmake.json'
GITMAKE_MSG = '[GITMAKE] '

try:
    import colorama
    colorama.init()
    def message(s):
        print colorama.Fore.CYAN + GITMAKE_MSG + s + colorama.Fore.RESET
    def error(s):
        print colorama.Fore.CYAN + GITMAKE_MSG + colorama.Fore.RED + s + colorama.Fore.RESET
except:
    def message(s):
        print GITMAKE_MSG + s
    def error(s):
        return message(s)
    error('No colorama support.  Install colorama for console coloring.')

class VersionInfo(object):
    def __init__(self,major=0,minor=0,patch=0,branch='dev'):
        self.major = int(major)
        self.minor = int(minor)
        self.patch = int(patch)
        self.branch = str(branch)
    def dict(self):
        return {'major':self.major, 'minor':self.minor, 'patch':self.patch, 'branch':self.branch }
    @staticmethod
    def from_string(s):
        m= re.match(r'v(\d+)\.(\d+)\.(\d+)-(\w+)', s)
        return VersionInfo(*m.groups())
    def rev_major(self, branch=None):
        return VersionInfo(self.major+1,0,0,branch or self.branch)    
    def rev_minor(self, branch=None):
        return VersionInfo(self.major,self.minor+1,0,branch or self.branch)    
    def rev_patch(self, branch=None):
        return VersionInfo(self.major,self.minor,self.patch+1,branch or self.branch)   
    def __cmp__(self, x):
        if x.branch != self.branch:
            raise ValueError("Cannot compare two versions from different branches")
        return cmp(self.tag, x.tag)
    @property
    def tag(self):
        return 'v%d.%d.%d-%s' % (self.major, self.minor, self.patch, self.branch)
    def __str__(self):
        return "<VersionInfo: %s>" % self.tag
    def __repr__(self):
        return str(self)

def do(command, show=False):
    'Execute the provided command with the shell.  Show the output if specified. Return a tuple: (ret code, command output)'
    returncode = 0
    try:
        output = subprocess.check_output(command, shell=True)
    except subprocess.CalledProcessError, e:
        returncode = e.returncode
    if(show):
        print output
    return (returncode, output)

def do_all(command_list, show=False, stop_on_error=True):
    '''
    Call do() for each command in the provided list.  If specified, stop executing commands on a nonzero return code.
    Returns a tuple (ok, outputs) where ok is True for success and False for a failed command, and outputs is the list of do() outputs
    '''
    retval = []
    for command in command_list:
        errc, msg = do(command, show)
        retval.append((errc, msg))
        if errc != 0:
            return (False, msg), retval
    return (True,''), retval

def confirm(message, default=True):
    while True:
        v = raw_input(message + ' (Y/n)' if default else ' y/N').strip().lower()
        if not v:
            return default
        elif v.startswith('y'):
            return True
        elif v.startswith('n'):
            return False

def command_init(args, settings):
    'Function called from the "init" command line'
    message("Initializing build environment...")
    initialize_environment(args)
    message("Done.")

def get_git_url():
    'Get the remote origin URL for the git repository in the current directory'
    rc, url = do('git config --get remote.origin.url')
    return url.strip()

def get_git_branch():
    'Get the name of the current branch'
    rc, output = do('git branch')
    for line in output.split('\n'):
        if line.strip().startswith('*'):
            return line.lstrip('*').strip()
    raise Exception("Couldn't determine the current branch!")

def get_git_tags(branch=None):
    'Get the list of all release tags in the current git repository'
    if branch:
        rc, output = do('git tag -l v*.*.*-%s' % branch)
    else:
        rc, output = do('git tag -l v*.*.*-*')
    if rc != 0:
        raise Exception("Couldn't get list of tags: %s" % output)
    versions = [x.strip() for x in output.split('\n') if x.strip() != '']
    return sorted(map(lambda x : VersionInfo.from_string(x), versions))

def do_build_here(args, settings):
    ' Perform the build in the current directory '
    build_cmd = settings['target']['build_command']
    message("Building...")
    retcode, output = do(build_cmd)
    if retcode == 0:
       message("Build succeeded.")
       return True
    else:
       error("Build failed with error code %d" % retcode)
       return False

def do_clone_tag_here(args, settings):
    'Clone the remote origin of the current git repository to the current directory'
    url = get_git_url()
    message('Cloning repos %s and checking out tag %s to %s' % (url, args.tag, os.curdir))
    do('git clone %s .' % url)
    do('git checkout %s' % args.tag)

def do_make_build_dir_here(args, settings):
    'Delete the build directory if it already exists, and create a new one here.  Return the path to the build dir.'
    build_dir = settings['settings']['build_directory']
    message('Creating build directory here: %s' % os.path.abspath(build_dir))
    do('rm -Rf %s' % build_dir)
    if not os.path.exists(build_dir): os.makedirs(build_dir)
    return build_dir

def do_cleanup(args, settings):
    build_dir = settings['settings']['build_directory']
    message('Deleting build directory: %s' % os.path.abspath(build_dir))
    do('rm -Rf %s' % build_dir)

def do_create_tag_here(args, settings):
    msg = args.message
    get_git_tags()
    git_branch = get_git_branch()
    git_tags = get_git_tags(git_branch)
    if git_tags:
        current_version = git_tags[-1]
        message('Current version is %s.' % (current_version.tag))
    else:
        message('No previous releases.')
        current_version = VersionInfo(branch=git_branch)
        
    if args.major:
        new_version = current_version.rev_major(git_branch)
    elif args.minor:
        new_version = current_version.rev_minor(git_branch)
    elif args.patch:
        new_version = current_version.rev_patch(git_branch)
    else:
        error('No rev level specified for tag.')

    message('Tagged version will be %s.' % new_version.tag)

    work = ['git tag -a %s -m "%s"' % (new_version.tag, msg),
            'git push origin %s' % new_version.tag]
    message('Creating a tag for %s' % new_version.tag)
    
    (tag_ok, tag_err), msgs = do_all(work)
    if tag_ok:
        return True
    else:
        error(tag_err)
        return False

def command_build(args, settings):
    'Function called by the "build" command line'
    if args.tag:
        cwd = os.curdir
        build_dir = do_make_build_dir_here(args, settings)
        os.chdir(build_dir)
        do_clone_tag_here(args, settings)  
        do_build_here(args, settings)
    else:
        do_build_here(args, settings)

def command_tag(args, settings):
    'Function called by the "tag" command line'
    do_cleanup(args, settings)
    build_ok = do_build_here(args, settings)
    if build_ok:
        do_create_tag_here(args, settings) 
    
def command_release(args, settings):
    print get_git_tags()

def command_deploy(args, settings):
    pass

def save_version_file(version_info, filename):
    'Given the version info tuple and a format specifier, return a string in the specified metafile format'
    C_TEMPLATE = '#ifndef __VERSION_H__\n#define __VERSION_H__\n#define VERSION_MAJOR $major\n#define VERSION_MINOR $minor\n#define VERSION_PATCH $patch\n#define VERSION_BRANCH $branch\n#define VERSION_TIMESTAMP $timestamp\n#endif'
    JSON_TEMPLATE = '{"major":$major,"minor":$minor,"patch":$patch,"branch":"$branch","timestamp":$timestamp}'
    PYTHON_TEMPLATE = 'major = $major\nminor=$minor\npatch=$patch\nbranch="$branch",timestamp=$timestamp'
    templates = {'hpp': C_TEMPLATE, 'h' : C_TEMPLATE, 'json' : JSON_TEMPLATE, 'py' : PYTHON_TEMPLATE}
    ext = os.path.splitext(filename)[1].strip().lower()
    d = version_info.dict()
    d['timestamp'] = time.time()
    try:
        template = templates['ext']
    except:
        raise Exception('Unknown version metafile format: "%s" Valid formats are: %s' % (filename, templates.keys()))
    return string.Template(template).substitute(d)

def initialize_environment(args):
    'Create JSON default templates for project version and settings'
    ok = True
    if os.path.isfile(VERSION_FILENAME) and args.confirm:
        ok = confirm('File %s already exists. Are you sure you want to overwrite it?' % VERSION_FILENAME)    
    if(ok):
        # Create a default version info file and save it
        VersionInfo().save(VERSION_FILENAME)

    GITMAKE_TEMPLATE = {  
        'settings': {
            'build_directory' : '_build'
        },
        'target': {
            'project_name' : 'My Project',
            'project_description' : 'The default gitmake project description.',
            'build_command' : 'make',
            'clean_command' : 'make clean',
            'version_file' : 'version.json',
        }
    }
    ok = True
    if os.path.isfile(SETTINGS_FILENAME) and args.confirm:
        ok = confirm('File %s already exists. Are you sure you want to overwrite it?' % SETTINGS_FILENAME)    
    if(ok):
        with open(SETTINGS_FILENAME, 'w') as fp:
            json.dump(GITMAKE_TEMPLATE, fp, indent=4)

def load_settings():
    'Load the build settings from disk and return as a dictionary (or empty dict in the case of an error)'
    try:
        with open(SETTINGS_FILENAME) as fp:
            settings = json.load(fp)
    except Exception, e:
        print e
        settings = {}
    return settings

def check_environment():
    'Make sure the environment has all the prerequisites.'
    retcode, output = do('git --version')
    if retcode != 0:
        raise Exception("Failed environment check: %s" % output)

def parse_arguments():
    main_parser = argparse.ArgumentParser()
    subparsers = main_parser.add_subparsers(title="Command", description="The commands for gitmake.py are:", help="Command function")
    init_parser = subparsers.add_parser('init', help='Initialize the build environment')
    init_parser.set_defaults(func=command_init)
    
    build_parser = subparsers.add_parser('build', description='Perform a build')
    build_parser.set_defaults(func=command_build)
    group = build_parser.add_mutually_exclusive_group()
    group.add_argument('--local', action='store_true', help='Perform a build from the local source files.')
    group.add_argument('--from-tag', type=str, metavar='TAG', dest='tag', help='Check out the specified tag and perform the build from it. (Does not modify local source)')
    
    tag_parser = subparsers.add_parser('tag', help='Create a tag')
    tag_parser.set_defaults(func=command_tag)
    tag_parser.add_argument('--message', '-m', type=str, default='Auto generated tag from gitmake.py', help='Message to accompany tag.')
    group = tag_parser.add_mutually_exclusive_group()
    group.add_argument('--major', dest='major', action='store_true', default=False, help='Tag is for a major revision')
    group.add_argument('--minor', dest='minor', action='store_true', default=False, help='Tag is for a minor revision')
    group.add_argument('--patch', dest='patch', action='store_true', default=False, help='Tag is for a patch revision')

    release_parser = subparsers.add_parser('release', help='Create a release')
    release_parser.set_defaults(func=command_release)
    
    deploy_parser = subparsers.add_parser('deploy', help='Deploy the build')
    deploy_parser.set_defaults(func=command_deploy)
    
    all_parsers = (main_parser, init_parser, build_parser, tag_parser, release_parser, deploy_parser)
    for parser in all_parsers:
        parser.add_argument('--noconfirm', dest='confirm', action='store_false', default=True, help='Suppress any "Are you sure?" messages.')

    return main_parser.parse_args()

if __name__ == "__main__":
    arguments = parse_arguments()
    settings = load_settings()
    check_environment()
    arguments.func(arguments, settings)

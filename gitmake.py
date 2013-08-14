#!/usr/bin/env python

from contextlib import contextmanager
import time
import argparse
import json
import os
import sys
import subprocess
import re
import string
import zipfile
import StringIO

# Version of this script
version_info = (0,0,13,'master')
version_string = 'v%d.%d.%d-%s' % version_info

VERSION_FILENAME = 'version.json'
SETTINGS_FILENAME = 'gitmake.json'
GITMAKE_MSG = '[GITMAKE] '

try:
    import colorama
    colorama.init()
    def message(s):
        print colorama.Fore.CYAN + GITMAKE_MSG + str(s) + colorama.Fore.RESET
    def error(s):
        print colorama.Fore.CYAN + GITMAKE_MSG + colorama.Fore.RED + str(s) + colorama.Fore.RESET
    def command(s):
        print colorama.Fore.GREEN + str(s) + colorama.Fore.RESET
except:
    def message(s):
        print GITMAKE_MSG + str(s)
    def error(s):
        return message(s)
    def command(s):
        return message(s)
    error('No colorama support.  Install colorama for console coloring.')

@contextmanager
def cd(path):
    old_path = os.path.abspath(os.getcwd())
    new_path = os.path.abspath(path)
    if old_path == new_path:
        yield
    else:
        message("Changing to directory %s" % new_path)
        os.chdir(new_path)
        yield
        message("Changing to directory %s" % old_path)
        os.chdir(old_path)

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
        if m:
            return VersionInfo(*m.groups())
        else:
            raise ValueError('Invalid version string: %s' % s)
    def rev_major(self, branch=None):
        return VersionInfo(self.major+1,0,0,branch or self.branch)    
    def rev_minor(self, branch=None):
        return VersionInfo(self.major,self.minor+1,0,branch or self.branch)    
    def rev_patch(self, branch=None):
        return VersionInfo(self.major,self.minor,self.patch+1,branch or self.branch)   
    def __cmp__(self, x):
        if not isinstance(x, VersionInfo):
            raise TypeError('Cannot compare VersionInfo and "%s" object' % str(type(x)))
        if self.tag == x.tag:
            return 0
        if x.branch != self.branch:
            return cmp(self.branch, x.branch)
        for a,b in ((self.major, x.major),(self.minor, x.minor), (self.patch, x.patch)):
            c = cmp(a,b)
            if c != 0:
                return c
    @property
    def tag(self):
        return 'v%d.%d.%d-%s' % (self.major, self.minor, self.patch, self.branch)
    def __str__(self):
        return "<VersionInfo: %s>" % self.tag
    def __repr__(self):
        return str(self)

gitmake_version = VersionInfo(*version_info)

class GitRepos(object):
    def __init__(self, url=None, dir=None, remote=False):
        self.url = url or do('git config --get remote.origin.url', show=False)[1].strip()
        self.dir = os.path.abspath(dir) if dir else os.curdir
        self.remote = remote 
    def checkout(self, branch):
        with cd(self.dir):
            do('git checkout %s' % branch)

    def commit(self, all=False, msg=''):
        with cd(self.dir):
            do('git commit %s -m "%s"' % ('-a' if all else '', msg))

    def add(self, *files):
        files = ' '.join(['"'+os.path.abspath(file)+'"' for file in files])
        with cd(self.dir):
            do('git add %s' % files)

    def clone(self):
        do('git clone "%s" "%s"' % (self.url, self.dir))

    def get_branches(self):
        'Get the names of all branches.  The first one is the current branch'
        with cd(self.dir):
            rc, output = do('git branch -a', show=False)
            retval = []
            for line in output.split('\n'):
                if line.strip().startswith('*'):
                    current_branch = line.lstrip('*').strip()
                else:
                    branch = line.strip()
                    if branch:
                        retval.append(branch)
            return [current_branch] + retval

    def get_current_branch(self):
        return self.get_branches()[0]
        
    def get_tags(self, branch=None):
        with cd(self.dir):
            if branch:
                rc, output = do('git tag -l v*.*.*-%s' % branch, show=False)
            else:
                rc, output = do('git tag -l v*.*.*-*', show=False)
            if rc != 0:
                raise Exception("Couldn't get list of tags: %s" % output)
            versions = [x.strip() for x in output.split('\n') if x.strip() != '']
            retval = []
            for version in versions:
                try:
                    retval.append(VersionInfo.from_string(version))
                except:
                    pass
            retval.sort()
            return retval

    def push(self, branch='master', remote='origin'):
        cmd = 'git push %s %s' % (remote, branch)
        if self.remote:
            with cd(self.dir):
                do(cmd)
        else:
            message("Skipping remote operation: %s" % cmd)

    def create_orphan_branch(self, branch):
        with cd(self.dir):
            do_all(['git checkout --orphan %s' % branch, 'git rm -rf .'])
            with open('README','w') as fp:
                fp.write('This is the %s branch.' % branch)
            self.add('README')
            self.commit(msg='Initial commit')
            if self.remote:
                self.push(branch)

    def tag(self, tag, msg=''):
        with cd(self.dir):
            do('git tag -a %s -m "%s"' % (tag, msg or 'Tag auto generated by gitmake.py'))

def do(cmd, show=True):
    'Execute the provided command with the shell.  Show the output if specified. Return a tuple: (ret code, command output)'
    returncode = 0
    try:
        if show:
            command(cmd)
        output = subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError, e:
        returncode = e.returncode
        output = e.output
    if(show):
        print output,
    return (returncode, output)

def do_all(command_list, show=False, stop_on_error=True):
    '''
    Call do() for each command in the provided list.  If specified, stop executing commands on a nonzero return code.
    Returns a tuple (ok, outputs) where ok is True for success and False for a failed command, and outputs is the list of do() outputs
    which are themselves tuples: (error_code, stdout_output)
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
        v = raw_input(message + ' (Y/n) ' if default else ' (y/N) ').strip().lower()
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

def do_build_here(args, settings):
    ' Perform the build in the current directory '
    build_cmd = settings['build']['build_command']
    message("Building...")
    retcode, output = do(build_cmd)
    if retcode == 0:
       message("Build succeeded.")
       return True
    else:
       error("Build failed with error code %d" % retcode)
       return False

def do_clone_tag_here(args, settings, requested_version):
    'Clone the remote origin of the current git repository to the current directory'
    repos = GitRepos()
    url = repos.url
    tags = repos.get_tags()
    message('Cloning repos %s and checking out tag %s' % (url, requested_version.tag))
    repos.clone()
    if requested_tag in tags:
        repos.checkout(requested_version.tag)
    else:
        error('Cannot checkout %s: No such tag exists. (%s)' % (requested_version.tag,tags))
        sys.exit(1)
    
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

def do_collect_release_data_here(args, settings):
    'Collect all the specified files and return a ZipFile object'
    files = [os.path.abspath(f) for f in settings['release']['files']]
    s = StringIO.StringIO()
    with zipfile.ZipFile(s, 'w') as z:
        for file in files:
            z.write(file)
            message("Releasing this file: %s" % file)
    data = s.getvalue()
    s.close()
    return data

def do_create_tag_here(args, settings):
    msg = args.message
    repos = GitRepos(remote=args.remote)
    git_branch = repos.get_current_branch()
    git_tags = repos.get_tags(git_branch)
    version_file = settings['build']['version_file']
    
    # Get the latest released version
    if git_tags:
        current_version = git_tags[-1]
        message('Current version is %s.' % (current_version.tag))
    else:
        message('No previous releases.')
        current_version = VersionInfo(branch=git_branch)
        
    # Increment the version number
    if args.major:
        new_version = current_version.rev_major(git_branch)
    elif args.minor:
        new_version = current_version.rev_minor(git_branch)
    elif args.patch:
        new_version = current_version.rev_patch(git_branch)
    else:
        # TODO prompt here for major/minor/patch
        error('No rev level specified for tag.')

    
    # TODO : CHECK FOR A CLEAN REPOS HERE. DON'T ADD AND COMMIT A VERSION FILE IF THERE'S LOCAL CHANGES

    message('Committing version file "%s" for tag %s.' % (version_file, new_version.tag))
    save_version_file(new_version, version_file)
    repos.add(version_file)
    repos.commit(msg='Tag commit for %s generated by gitmake.py' % new_version.tag)

    message('Creating a commit and tag for %s' % new_version.tag)
    repos.tag(new_version.tag)
    repos.push(new_version.tag)

    message('Tag %s created successfully.' % new_version.tag)
    return new_version

def do_release(args, settings, release_version):
    'Function called by the "release" command line'
     
    # Create a build dir and go there
    build_dir = do_make_build_dir_here(args, settings) 
    current_dir = os.getcwd()
    os.chdir(build_dir)
    do_clone_tag_here(args, settings, release_version)
    repos = GitRepos(remote=args.remote)
    all_branches = repos.get_branches()
    if 'release' not in all_branches and 'remotes/origin/release' not in all_branches:
        create_release_branch = True
        if args.confirm:
            create_release_branch = confirm('No branch exists for releases.  Create one?', True)
        if create_release_branch:
            repos.create_orphan_branch('release')
    
    # step 1: collect files
    # step 2: create bundle
    s = do_collect_release_data_here(args, settings)
    
    # step 3: switch to release branch
    # step 4: check for existing release (error if so, or maybe prompt?)
    filename = settings['release']['filename'] + release_version.tag + '.zip'
    repos.checkout('release')
    if os.path.exists(filename):
        error('Release bundle %s already exists.' % filename)
        sys.exit(1)

    # step 5: save if all looks good, add, commit push
    message('Saving release bundle as %s' % filename)
    with open(filename, 'wb') as fp:
        fp.write(s)
    message('Committing release %s to repository...' % release_version.tag)
    repos.add(filename)
    repos.commit(msg='Release of %s' % release_version.tag)
    message('Pushing commit to remote...')
    repos.push('release')
    repos.checkout('master')
    os.chdir(current_dir)

def command_build(args, settings):
    'Function called by the "build" command line'
    if args.tag:
        cwd = os.curdir
        build_dir = do_make_build_dir_here(args, settings)
        with cd(build_dir):
            do_clone_tag_here(args, settings, VersionInfo.from_string(args.tag))  
            do_build_here(args, settings)
    else:
        save_version_file(VersionInfo(), settings['build']['version_file'])
        do_build_here(args, settings)

def command_tag(args, settings):
    'Function called by the "tag" command line'
    do_cleanup(args, settings)
    
    # Build first in order to determine if it's OK to tag
    ok_to_tag = do_build_here(args, settings)
    if not ok_to_tag and args.confirm:
        ok_to_tag = confirm("The build failed.  Are you sure you want to create a tag here? (y/N)", False)
    
    if ok_to_tag:
        new_version = do_create_tag_here(args, settings) 
    
        if args.release:
            do_release(args, settings, new_version)


def command_release(args, settings):
    version = VersionInfo.from_string(args.tag)
    do_release(args, settings, version)

def command_deploy(args, settings):
    # step 1 execute deploy 
    error('Deploy functionality not implemented yet.')

def command_clean(args, settings):
    'Function called by the "clean" command line'
    message("Running the clean command...")
    do_cleanup(args, settings)
    do(settings['build']['clean_command'])
    message("Cleaning complete.")

def save_version_file(version_info, filename):
    'Take the version info provided and write to file.  File format is determined from the extension of the filename given.'
    C_TEMPLATE = '#ifndef __VERSION_H__\n#define __VERSION_H__\n#define VERSION_MAJOR $major\n#define VERSION_MINOR $minor\n#define VERSION_PATCH $patch\n#define VERSION_BRANCH $branch\n#define VERSION_TIMESTAMP $timestamp\n#endif'
    JSON_TEMPLATE = '{"major":$major,"minor":$minor,"patch":$patch,"branch":"$branch","timestamp":$timestamp}'
    PYTHON_TEMPLATE = 'major = $major\nminor=$minor\npatch=$patch\nbranch="$branch"\ntimestamp=$timestamp'
    templates = {'hpp': C_TEMPLATE, 'h' : C_TEMPLATE, 'json' : JSON_TEMPLATE, 'py' : PYTHON_TEMPLATE}
    ext = os.path.splitext(filename)[1].strip().lstrip('.').lower()
    d = version_info.dict()
    d['timestamp'] = time.time()
    try:
        template = templates[ext]
    except:
        raise Exception('Unknown version file format: "%s" Valid formats are: %s' % (ext, templates.keys()))
    with open(filename, 'w') as fp:    
        fp.write(string.Template(template).substitute(d))

def initialize_environment(args):
    'Create JSON default templates for project version and settings'
    ok = True

    GITMAKE_TEMPLATE = {  
        'settings': {
            'build_directory' : '_build'
        },
        'project': {
            'name' : 'My Project',
            'description' : 'The default gitmake project description.',
        },
        'build' : {
            'build_command' : 'make',
            'clean_command' : 'make clean',
            'version_file' : 'version.json'
        },
        'release' : {
            'files' : [],
            'format' : 'zip',
            'filename' : 'myproject'
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
        error(e)
        settings = {}
    return settings

def check_environment():
    'Make sure the environment has all the prerequisites.'
    retcode, output = do('git --version',show=False)
    if retcode != 0:
        raise Exception("Failed environment check: %s" % output)
    # TODO check here for the ability to commit and push and whatnot

def parse_arguments():
    main_parser = argparse.ArgumentParser()
    main_parser.add_argument('--version', '-v', action='version', version=version_string)
    
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
    tag_parser.add_argument('--release', '-r', action='store_true', help='Perform a release after tagging.', default=False)
    
    release_parser = subparsers.add_parser('release', help='Create a release')
    release_parser.set_defaults(func=command_release)
    release_parser.add_argument('--from-tag', type=str, metavar='TAG', dest='tag', help='Check out the specified tag and perform the release from it. (Does not modify local source)')
    
    deploy_parser = subparsers.add_parser('deploy', help='Deploy the build')
    deploy_parser.set_defaults(func=command_deploy)
   
    clean_parser = subparsers.add_parser('clean', help='Clean the build')
    clean_parser.set_defaults(func=command_clean)

    all_parsers = (main_parser, init_parser, build_parser, tag_parser, release_parser, deploy_parser, clean_parser)
    for parser in all_parsers:
        parser.add_argument('--noconfirm', dest='confirm', action='store_false', default=True, help='Suppress any "Are you sure?" messages.')
        parser.add_argument('--noremote', dest='remote', action='store_false', default=True, help='Skip any git operations that push changes to a remote')
    return main_parser.parse_args()

if __name__ == "__main__":
    arguments = parse_arguments()
    settings = load_settings()
    check_environment()
    try:
        arguments.func(arguments, settings)
    except Exception, e:
        error(str(e))
        raise e
    message("Finished.")

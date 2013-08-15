Gitmake
=======
Gitmake is a configurable script that automates the process of tagging and releasing your code.  Gitmake isn't a replacement for make, cmake, scons, or whatever you currently use to build your code.  It simply strives to make it easy to tag and release code using git.

Philosophy
----------
Gitmake assumes that you have your code in a git repository, and want to perform releases periodically.  Releases are stored as annotated tags in git, and each release has a version number.  The version numbering scheme follows the semantic versioning standard, with a major, minor, and patch level associated with each version.  In addition to the three version numbers, the current branch is recorded as a part of the release, giving a version string of the form vX.Y.Z-branch where X,Y, and Z are the major, minor, and patch levels respectively.  In addition to tagging the source of releases, gitmake manages a *release* branch, which is a dedicated orphan branch that is a location to store released files, such as binary executables and documentation generated as part of a build.  Using the release branch, compiled products of the build can be kept out of the master branch, but still stored in git for easy access.

Getting Started
---------------
To build your project with gitmake, copy gitmake.py into your project's root directory.  To create a default configuration file:

`python gitmake.py init`

You can edit the default configuration and substitute the settings for your build.  The options are fairly self explanatory.

Build Locally
-------------
Once you have installed gitmake in your project and created a configuration file, you can build from local source:

`python gitmake.py build --local`

Not much to it.  This just calls the build script you specified in your configuration file.

Create a Release Tag
--------------------
When you are happy with your build, you can create a release tag:

`python gitmake.py tag`

Gitmake will prompt you for the type of release you are tagging (major, minor, patch). If you like, you can specify --major, --minor, or --patch on the command line as an argument to the tag command, rather than being prompted:

`python gitmake.py tag --minor`

Release tags are immediately pushed to the current remote, unless the `--noremote` option is used.

Building from an Already-Created Release Tag
--------------------------------------------
Release tags that have already been created can be fetched and built any time, by specifying the tag to the build command:

`python gitmake.py build --from-tag=v1.2.3-master`

When --from-tag is specified, the build command will create a clean build directory, clone the repository into it, checkout the specified tag and perform a build there.

Release
-------
To create a release bundle, use the release command:

`python gitmake.py release --from-tag=v1.2.3-master`

The command above will fetch and build the tag v1.2.3-master.  If the build is successful, the build products will be bundled and copied to the *release* branch under the release version name.

Tag and Release Workflow
------------------------
To create a tag and immediately generate a release bundle from it, you can pass the --release switch to the `tag` command:

python gitmake.py tag --release

This will perform the tag operation (prompting you for a rev level) and if successful, perform a release operation afterward, as if you had issued the `release` command.

Version File
------------
It's frequently handy for a build to track it's own version number and include it in the code.  If specified, a version file will be created when tagging a release that specifies the major, minor, patch, and branch fields of the version string.  The format of the version file will be derived from its extension.  The currently supported formats are C/C++, JSON, and Python.

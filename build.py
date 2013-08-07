import version

print "Reading gitmake.py..."
with open('gitmake.py') as fp:
    lines = fp.readlines()

print "Rewriting gitmake.py..."
with open('gitmake.py', 'w') as fp:
    for line in lines:
        if line.startswith('version_info ='):
            fp.write('version_info = (%d,%d,%d,\'%s\')\n' % (version.major, version.minor, version.patch, version.branch))
	else:
            fp.write(line)

print "Done!"

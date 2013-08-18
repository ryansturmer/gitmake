import version
import os

OUTPUT_DIR = './_output'
print "Reading gitmake.py..."
with open('gitmake.py') as fp:
    lines = fp.readlines()

print "Creating output directory '%s'" % OUTPUT_DIR
if not os.path.exists(OUTPUT_DIR):
    os.mkdir(OUTPUT_DIR)

print "Writing %s/gitmake.py..." % OUTPUT_DIR
with open(OUTPUT_DIR+'/gitmake.py', 'w') as fp:
    for line in lines:
        if line.startswith('version_info ='):
            fp.write('version_info = (%d,%d,%d,\'%s\')\n' % (version.major, version.minor, version.patch, version.branch))
	else:
            fp.write(line)

print "Done!"

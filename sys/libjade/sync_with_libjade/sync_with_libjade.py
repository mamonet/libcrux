import subprocess
import shutil
import os
import jinja2

DEBUG = 0

LIBJADE_GIT_URL = "https://github.com/formosa-crypto/libjade"

ALGORITHMS = {
    'hashes': [{
        'name': 'sha256',
        'implementations': [
            {
                'name': 'ref',
                'platforms': ['amd64'],
            }
        ]
    }]
}

def shell(command, expect=0):
    subprocess_stdout = None if DEBUG > 0 else subprocess.DEVNULL

    ret = subprocess.run(command, stdout=subprocess_stdout, stderr=subprocess_stdout)
    if ret.returncode != expect:
        raise Exception("'{}' failed with error {}. Expected {}.".format(" ".join(command), ret, expect))

def file_get_contents(filepath, encoding=None):
    with open(filepath, mode='r', encoding=encoding) as fh:
        return fh.read()

def file_put_contents(filepath, s, encoding=None):
    with open(filepath, mode='w', encoding=encoding) as fh:
        fh.write(s)

def output_header(input_file, output_file, encoding=None):
    with open(input_file, mode='r', encoding=encoding) as in_fh, open(output_file, mode='w', encoding=encoding) as out_fh:
        for line in in_fh:
            if line.startswith('#define') or line.startswith('#ifndef'):
                out_fh.write(line.upper())
            else:
                out_fh.write(line)

def replacer(filepath, instructions, delimiter, fragmentname):
    contents = file_get_contents(filepath)

    template = file_get_contents(fragmentname + '.fragment')

    identifier_start = '{} SYNC_WITH_LIBJADE_GENERATE_{}_START'.format(delimiter, fragmentname.upper())
    identifier_end = '{} SYNC_WITH_LIBJADE_GENERATE_{}_END'.format(delimiter, fragmentname.upper())

    preamble = contents[:contents.find(identifier_start)]
    postamble = contents[contents.find(identifier_end):]

    contents = preamble + identifier_start + jinja2.Template(template).render(
        {'instructions': instructions}) + postamble

    file_put_contents(filepath, contents)

if __name__ == '__main__':
    crate_root = "/Users/wxyz/cryspen/libcrux/sys/libjade"
    libjade_dir = os.path.join(crate_root, 'sync_with_libjade', 'libjade')
    libjade_dotgit = os.path.join(libjade_dir, '.git')


    if not os.path.exists(libjade_dotgit):
        shell(['git', 'init', libjade_dir])
        shell(['git', '--git-dir', libjade_dotgit, 'remote', 'add', 'origin', LIBJADE_GIT_URL])

    shell(['git', '--git-dir', libjade_dotgit, '--work-tree', libjade_dir, 'remote', 'set-url', 'origin', LIBJADE_GIT_URL])
    shell(['git', '--git-dir', libjade_dotgit, '--work-tree', libjade_dir, 'fetch'])
    shell(['git', '--git-dir', libjade_dotgit, '--work-tree', libjade_dir, 'checkout', 'latest'])

    for hash_alg in ALGORITHMS['hashes']:
        for implementation in hash_alg['implementations']:
            for platform in implementation['platforms']:
                alg_dir = os.path.join(libjade_dir, 'src', 'crypto_hash', hash_alg['name'], platform, implementation['name'])
                os.chdir(alg_dir)
                shell(['make', 'clean']) # TODO: Investigate why this is needed.
                shell(['make'])
                shutil.copyfile('hash.s',
                                os.path.join(crate_root, 'jazz', '{}_{}.s'.format(hash_alg['name'], implementation['name'])))

                output_header(os.path.join('include', 'api.h'),
                                os.path.join(crate_root, 'jazz', 'include', '{}_{}.h'.format(hash_alg['name'], implementation['name'])))
                os.chdir(os.path.join(crate_root, 'sync_with_libjade'))


    replacer(os.path.join(crate_root, 'jazz', 'include', 'libjade.h'), ALGORITHMS, '/////', 'header_names')
    replacer(os.path.join(crate_root, 'build.rs'), ALGORITHMS, '/////', 'assembly_filenames')


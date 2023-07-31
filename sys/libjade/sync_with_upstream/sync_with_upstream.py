import subprocess
import shutil
import os
import jinja2

DEBUG = 0

LIBJADE_GIT_URL = "https://github.com/formosa-crypto/libjade"

IMPLEMENTATIONS = {
    'hashes': [
        {
            'name': 'sha256',
            'allowlist_prefix': 'jade_hash_.*',
            'platforms': {
                'amd64': ['ref']
            }
        },
        {
            'name': 'sha3-224',
            'allowlist_prefix': 'jade_hash_sha3_224_.*',
            'platforms': {
                'amd64': ['ref', 'avx2']
            }
        }
    ]
}

def shell(command, expect=0, cwd=None):
    subprocess_stdout = None if DEBUG > 0 else subprocess.DEVNULL

    ret = subprocess.run(command, stdout=subprocess_stdout, stderr=subprocess_stdout, cwd=cwd)
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
            if line.startswith('#ifndef') or line.startswith('#define'):
                line_split = line.split()

                if len(line_split) == 3 and not ('ALGNAME' in line or 'BYTES' in line):
                    continue

                line_split[1] = line_split[1].upper()
                out_fh.write(' '.join(line_split) + '\n')
            else:
                out_fh.write(line)

def replacer(filepath, instructions, delimiter, fragmentname):
    contents = file_get_contents(filepath)

    template = file_get_contents(fragmentname + '.fragment')

    identifier_start = '{} SYNC_WITH_UPSTREAM_GENERATE_{}_START'.format(delimiter, fragmentname.upper())
    identifier_end = '{} SYNC_WITH_UPSTREAM_GENERATE_{}_END'.format(delimiter, fragmentname.upper())

    preamble = contents[:contents.find(identifier_start)]
    postamble = contents[contents.find(identifier_end):]

    contents = preamble + identifier_start + jinja2.Template(template).render(
        {'instructions': instructions}) + postamble

    file_put_contents(filepath, contents)

if __name__ == '__main__':
    crate_root = "/Users/wxyz/cryspen/libcrux/sys/libjade"

    libjade_dir = os.path.join(crate_root, 'sync_with_upstream', 'libjade')
    libjade_dotgit = os.path.join(libjade_dir, '.git')

    if not os.path.exists(libjade_dotgit):
        shell(['git', 'init', libjade_dir])
        shell(['git', '--git-dir', libjade_dotgit, 'remote', 'add', 'origin', LIBJADE_GIT_URL])

    shell(['git', '--git-dir', libjade_dotgit, '--work-tree', libjade_dir, 'remote', 'set-url', 'origin', LIBJADE_GIT_URL])
    shell(['git', '--git-dir', libjade_dotgit, '--work-tree', libjade_dir, 'fetch'])
    shell(['git', '--git-dir', libjade_dotgit, '--work-tree', libjade_dir, 'checkout', 'latest'])

    for hash_alg in IMPLEMENTATIONS['hashes']:
        for platform, implementations in hash_alg['platforms'].items():
            for implementation in implementations:
                alg_dir = os.path.join(libjade_dir, 'src', 'crypto_hash', hash_alg['name'], platform, implementation)

                # TODO: libjade errors without this sometimes; look closer into
                # why.
                shell(['make', 'clean'], cwd = alg_dir) 

                shell(['make'], cwd = alg_dir)

                jazz_dir = os.path.join(crate_root, 'jazz')
                shutil.copyfile(os.path.join(alg_dir, 'hash.s'),
                                os.path.join(jazz_dir, '{}_{}.s'.format(hash_alg['name'].replace('-', '_'), implementation)))

                output_header(os.path.join(alg_dir, 'include', 'api.h'),
                                os.path.join(jazz_dir, 'include', '{}_{}.h'.format(hash_alg['name'].replace('-', '_'), implementation)))


    replacer(os.path.join(crate_root, 'jazz', 'include', 'libjade.h'), IMPLEMENTATIONS, '/////', 'ref_header_names')
    replacer(os.path.join(crate_root, 'jazz', 'include', 'libjade.h'), IMPLEMENTATIONS, '/////', 'avx2_header_names')
    replacer(os.path.join(crate_root, 'build.rs'), IMPLEMENTATIONS, '/////', 'ref_assembly_filenames')
    replacer(os.path.join(crate_root, 'build.rs'), IMPLEMENTATIONS, '/////', 'avx2_assembly_filenames')
    replacer(os.path.join(crate_root, 'build.rs'), IMPLEMENTATIONS, '/////', 'allowlist')

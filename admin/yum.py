# Copyright Hybrid Logic Ltd.  See LICENSE file for details.

"""
Effectful interface to RPM tools.
"""

import os

import requests
from requests_file import FileAdapter
from characteristic import attributes
from effect import Effect, sync_performer, TypeDispatcher
from effect.do import do
from subprocess import check_call


@attributes([
    "source_repo",
    "target_path",
    "packages",
    "flocker_version",
    "distro_name",
    "distro_version",
])
class DownloadPackagesFromRepository(object):
    """
    Download a given set of RPMs from a repository.

    :ivar bytes source_repo: Location of repoisitory.
    :ivar FilePath target_path: Directory to download packages to.
    :ivar list packages: List of bytes, package names to download.

    # TODO document new params
    """


@sync_performer
def perform_download_packages_from_repository(dispatcher, intent):
    """
    See :class:`DownloadPackagesFromRepository`.
    """
    # TODO move make_rpm_version to somewhere shared
    from release import make_rpm_version
    from admin.packaging import Distribution, package_filename

    rpm_version = make_rpm_version(intent.flocker_version)
    distribution = Distribution(
        name=intent.distro_name,
        version=intent.distro_version,
    )
    package_type = distribution.package_type()
    package_to_architecture = {
        'clusterhq-flocker-cli': 'all',
        'clusterhq-flocker-node': 'all',
        'clusterhq-python-flocker': 'native',
    }
    s = requests.Session()
    # Tests use a local package repository
    s.mount('file://', FileAdapter())

    downloaded_packages = set()
    for package in intent.packages:
        package_name = package_filename(
            package_type=package_type,
            package=package,
            architecture=package_to_architecture[package],
            rpm_version=rpm_version,
        )
        url = intent.source_repo + '/' + package_name
        local_path = intent.target_path.child(package_name).path
        with open(local_path, "wb") as local_file:
            local_file.write(s.get(url).content)
        downloaded_packages.add(package_name)

    return downloaded_packages


@attributes([
    "repository_path",
])
class CreateRepo(object):
    """
    Create repository metadata.

    Note that this returns a list with the prefixes stripped.

    :ivar FilePath repository_path: Location of rpm files to create a
        repository from.
    """


@sync_performer
def perform_create_repository(dispatcher, intent):
    """
    See :class:`CreateRepo`.

    :return: List of new and modified rpm metadata filenames.
    """
    check_call([
        b'createrepo',
        b'--update',
        b'--quiet',
        intent.repository_path.path])
    # TODO share this logic via ListMetadata
    return set([os.path.basename(path.path) for path in
                intent.repository_path.child('repodata').walk()])


@attributes([
    "repository_path",
])
class ListMetadata(object):
    """
    List the filenames of repository metadata.

    Note that this returns a set with the prefixes stripped.

    :ivar FilePath repository_path: Location of repository to list repository
         metadata from.
    """


@sync_performer
def perform_list_metadata(dispatcher, intent):
    """
    See class:`ListMetadata`.
    """
    return set([os.path.basename(path.path) for path in
                intent.repository_path.child('repodata').walk()])

yum_dispatcher = TypeDispatcher({
    DownloadPackagesFromRepository: perform_download_packages_from_repository,
    ListMetadata: perform_list_metadata,
    CreateRepo: perform_create_repository,
})


class FakeYum(object):
    """
    Enough of a fake implementation of yum utilities to test
    :func:`admin.release.upload_rpms`.
    """
    @sync_performer
    def _perform_create_repository(self, dispatcher, intent):
        """
        See :class:`CreateRepo`.
        """
        metadata_directory = intent.repository_path.child('repodata')
        metadata_directory.createDirectory()
        packages = set([
            os.path.basename(path.path) for path in
            intent.repository_path.walk() if path.isfile()])
        for filename in ['repomd.xml', 'filelists.xml.gz', 'other.xml.gz',
                         'primary.xml.gz']:
            metadata_directory.child(filename).setContent(
                'metadata content for: ' + ','.join(packages))
        return set([os.path.basename(path.path) for path in
                    intent.repository_path.child('repodata').walk()])

    def get_dispatcher(self):
        """
        Get an :module:`effect` dispatcher for interacting with this
        :class:`FakeYum`.
        """
        return TypeDispatcher({
            DownloadPackagesFromRepository:
                perform_download_packages_from_repository,
            ListMetadata: perform_list_metadata,
            CreateRepo: self._perform_create_repository,
        })

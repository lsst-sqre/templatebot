"""Management of the template repository.
"""

import shutil
import uuid

import git
from templatekit.repo import Repo


class RepoManager:
    """A class that manages the cloned tempate repositories for different
    git refs.

    Parameters
    ----------
    url : `str`
        URL of a templatekit-compatible Git repository.
    cache_dir : `pathlib.Path`
        Directory containing the cloned template repositories for all Git SHAs.
    logger
        ``structlog`` logger instance.
    """

    def __init__(self, *, url, cache_dir, logger):
        self._logger = logger
        self._url = url
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(exist_ok=True)

        self._clones = {}  # keys are SHAs, values are Paths to the clone
        self._clone_refs = {}  # map branches/tags to SHAs

    def clone(self, gitref='master'):
        """Clone the template repository corresponding to Git ref.

        Parameters
        ----------
        gitref : `str`
            A git ref (branch, tag, or SHA string) of the template repsitory.

        Returns
        -------
        path : `pathlib.Path`
            Path of the template repository clone.
        """
        # Make a unique directory for this clone
        clone_dir = self._cache_dir / str(uuid.uuid4())
        logger = self._logger.bind(git_ref=gitref, dirname=str(clone_dir))
        logger.info('Cloning template repo')
        repo = git.Repo.clone_from(
            self._url,
            str(clone_dir),
            branch=gitref,
            depth=1,
            recurse_submodules=True,
            shallow_submodules=True)
        head_sha = repo.head.reference.commit.hexsha
        logger.info('Resolved SHA of template repo clone', sha=head_sha)

        if head_sha in self._clones:
            # Already cloned this SHA
            shutil.rmtree(str(clone_dir))
        else:
            self._clones[head_sha] = clone_dir

        # Update the mapping of gitref to SHA. This should always be good to
        # do since multiple symbolic references (tags and branches) might
        # always point to the same SHA
        self._clone_refs[gitref] = head_sha

        return self._clones[head_sha]

    def get_checkout_path(self, gitref):
        """Get the path to a cloned repositoryy for a given Git ref.

        If a clone is available, the method makes a new clone.

        Parameters
        ----------
        gitref : `str`
            A git ref (branch, tag, or SHA string) of the template repsitory.

        Returns
        -------
        path : `pathlib.Path`
            Path of the template repository clone.
        """
        if gitref in self._clones:
            return self._clones[gitref]
        elif gitref in self._clone_refs:
            return self._clones[self._clone_refs[gitref]]
        else:
            return self.clone(gitref=gitref)

    def get_repo(self, gitref):
        """Open a repo clone with templatekit.

        Parameters
        ----------
        gitref : `str`
            A git ref (branch, tag, or SHA string) of the template repository.

        Returns
        -------
        repo : `templatekit.repo.Repo`
            Template repository.
        """
        path = self.get_checkout_path(gitref=gitref)
        return Repo(path)

    def delete_all(self):
        """Delete all cloned repositories from the filesystem.
        """
        self._logger.info('Deleting clones', dirname=self._cache_dir)
        shutil.rmtree(str(self._cache_dir))
        # Also reset internal pointer caches
        self._clones = {}
        self._clone_refs = {}

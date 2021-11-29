"""Management of the template repository."""

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

    def clone(self, gitref="master"):
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
        logger.info("Cloning template repo")
        repo = git.Repo.clone_from(
            self._url,
            str(clone_dir),
            branch=gitref,
            depth=1,
            recurse_submodules=True,
            shallow_submodules=True,
        )
        head_sha = repo.head.reference.commit.hexsha
        logger.info("Resolved SHA of template repo clone", sha=head_sha)

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
        """Get the path to a cloned repository for a given Git ref.

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
            # The gitref is a SHA that's already been cloned.
            return self._clones[gitref]
        elif gitref in self._clone_refs:
            # The gitref is a branch or tag name that's been cloned, but
            # needs to be mapped to a SHA.
            self._refresh_checkout(gitref)
            return self._clones[self._clone_refs[gitref]]
        else:
            # No record of this gitref; need to make a new clone
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
        """Delete all cloned repositories from the filesystem."""
        self._logger.info("Deleting clones", dirname=self._cache_dir)
        shutil.rmtree(str(self._cache_dir))
        # Also reset internal pointer caches
        self._clones = {}
        self._clone_refs = {}

    def _refresh_checkout(self, gitref):
        """Checks if the Git origin has a new SHA associated with its head,
        and if so, creates a new clone with that SHA.
        """
        existing_sha = self._clone_refs[gitref]
        existing_repo_path = self._clones[existing_sha]
        repo = git.Repo(path=str(existing_repo_path))
        origin = repo.remotes[0]  # the only remote is origin
        for fetch_info in origin.fetch():
            if fetch_info.ref.name == f"origin/{gitref}":
                if fetch_info.commit.hexsha != existing_sha:
                    self._logger.info(
                        f"{gitref} updated from {existing_sha} to "
                        f"{fetch_info.commit.hexsha}; re-cloning"
                    )
                    # The origin branch points to a different commit. This
                    # clones it, which also updates the self._clone_refs
                    # mapping.
                    self.clone(gitref=gitref)

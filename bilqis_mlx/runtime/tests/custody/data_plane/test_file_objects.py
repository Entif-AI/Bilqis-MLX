"""Immutable file ownership, racing adoption and directory durability."""
import hashlib
import multiprocessing
import os
from unittest.mock import patch

from bilqis_mlx._data_plane import file_objects
from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.runtime.tests.custody.data_plane.base import DataPlaneCase


def _racing_adopter(source, digest, barrier, results):
    plane = data_plane()
    link = os.link

    def synchronized_link(origin, destination):
        barrier.wait(timeout=15)
        return link(origin, destination)

    try:
        with patch.object(file_objects.os, "link", side_effect=synchronized_link):
            results.put(str(plane.adopt_file_object(source, digest)))
    except Exception as error:
        results.put(repr(error))


class FileObjectTests(DataPlaneCase):
    def source(self):
        source = self.root / "source.safetensors"
        source.write_bytes(b"immutable tensor bytes")
        return source, hashlib.sha256(source.read_bytes()).hexdigest()

    def test_adoption_owns_bytes_independently_of_source_aliases(self):
        source, digest = self.source()
        alias = self.root / "alias"
        os.link(source, alias)
        target = data_plane().adopt_file_object(source, digest)
        alias.write_bytes(b"caller changed source")
        self.assertEqual(data_plane().require_file_object(digest), target)
        self.assertEqual(target.read_bytes(), b"immutable tensor bytes")

    def test_competing_install_verifies_and_reuses_winner(self):
        source, digest = self.source()
        plane = data_plane()
        target = plane.file_object_destination(digest)
        link = os.link

        def competing_link(origin, destination):
            link(origin, destination)
            raise FileExistsError(destination)

        with patch.object(file_objects.os, "link", side_effect=competing_link):
            self.assertEqual(plane.adopt_file_object(source, digest), target)
        self.assertEqual(plane.require_file_object(digest), target)

    def test_adoption_syncs_directory_ancestry_including_reuse(self):
        source, digest = self.source()
        plane = data_plane()
        target = plane.file_object_destination(digest)
        for unused in range(2):
            with patch.object(file_objects, "_fsync_directory") as sync:
                plane.adopt_file_object(source, digest)
            synced = [call.args[0] for call in sync.call_args_list]
            for directory in (target.parent, target.parent.parent, self.root.resolve()):
                self.assertIn(directory, synced)

    def test_independent_process_writers_converge_on_one_object(self):
        source, digest = self.source()
        plane = data_plane()
        context = multiprocessing.get_context("spawn")
        barrier, results = context.Barrier(2), context.Queue()
        workers = [context.Process(target=_racing_adopter,
                                   args=(source, digest, barrier, results))
                   for unused in range(2)]
        try:
            for worker in workers:
                worker.start()
            target = plane.file_object_destination(digest)
            self.assertEqual([results.get(timeout=25) for unused in workers],
                             [str(target), str(target)])
            for worker in workers:
                worker.join(timeout=5)
                self.assertEqual(worker.exitcode, 0)
            self.assertEqual(plane.require_file_object(digest), target)
            self.assertEqual(list(target.parent.iterdir()), [target])
        finally:
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                    worker.join()
            results.close()


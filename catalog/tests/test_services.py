import threading
import unittest

from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from catalog import services
from catalog.models import File, Storage
from catalog.tests.factories import TempMediaMixin, make_category, make_file, upload


def set_quota(quota_bytes: int) -> None:
    Storage.load()
    Storage.objects.filter(pk=1).update(quota_bytes=quota_bytes)


class QuotaTests(TempMediaMixin, TestCase):
    def test_reserve_space_within_quota(self):
        file = make_file(content=b"x" * 600)
        set_quota(1000)
        with transaction.atomic():
            services.reserve_space(400)
            with self.assertRaises(services.QuotaExceeded) as error:
                services.reserve_space(401)
        self.assertEqual(error.exception.code, "quota")
        self.assertIn("400", str(error.exception))
        # Replacing a file frees its own size first.
        with transaction.atomic():
            services.reserve_space(1000, replacing=file)

    def test_zero_quota_means_no_limit(self):
        set_quota(0)
        with transaction.atomic():
            services.reserve_space(10**15)
        self.assertEqual(services.storage_summary().percent, 0.0)

    def test_add_file_checks_the_quota(self):
        category = make_category()
        set_quota(10)
        with self.assertRaises(services.QuotaExceeded):
            services.add_file(title="Big", category=category, upload=upload("big.bin", b"x" * 11))
        self.assertFalse(File.objects.exists())
        file = services.add_file(
            title="Small", category=category, upload=upload("a.txt", b"x" * 10), description="d"
        )
        self.assertEqual((file.size, file.description), (10, "d"))

    def test_summary(self):
        make_file(content=b"x" * 250)
        set_quota(1000)
        summary = services.storage_summary()
        self.assertEqual((summary.used, summary.quota, summary.percent), (250, 1000, 25.0))
        set_quota(100)
        self.assertEqual(services.storage_summary().percent, 100.0)

    @override_settings(STORAGE_QUOTA_BYTES=0)
    def test_used_bytes_with_no_files(self):
        self.assertEqual(services.used_bytes(), 0)


@unittest.skipUnless(connection.vendor == "postgresql", "row locks need PostgreSQL")
class ConcurrentUploadTests(TempMediaMixin, TransactionTestCase):
    """Two uploads race for the last free bytes. Exactly one of them may win."""

    def test_reserve_space_needs_a_transaction(self):
        with self.assertRaises(transaction.TransactionManagementError):
            services.reserve_space(1)

    def test_only_one_upload_fits(self):
        category = make_category()
        set_quota(1000)
        barrier = threading.Barrier(2)
        results = []

        def attempt(name):
            try:
                barrier.wait()
                services.add_file(title=name, category=category, upload=upload(name, b"x" * 700))
                results.append("saved")
            except services.QuotaExceeded:
                results.append("rejected")
            finally:
                connections.close_all()

        threads = [threading.Thread(target=attempt, args=(f"{i}.bin",)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(results), ["rejected", "saved"])
        self.assertEqual(File.objects.count(), 1)

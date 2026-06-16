import unittest

import gold_supabase_repo as gsr


class TransactionPayloadTests(unittest.TestCase):
    def test_build_transaction_payload_for_try_purchase(self):
        payload = gsr.build_transaction_payload(
            p_date="2024-01-01",
            g_weight=3,
            c_raw=7336875.0,
            fx_rate=32.5,
            currency="TRY",
        )

        self.assertEqual(payload["purchase_date"], "2024-01-01")
        self.assertEqual(payload["grams"], 3.0)
        self.assertEqual(payload["cost_try"], 7336875.0)
        self.assertEqual(payload["cost_usd"], 225750.0)

    def test_build_transaction_payload_for_usd_purchase(self):
        payload = gsr.build_transaction_payload(
            p_date="2024-01-01",
            g_weight=3,
            c_raw=225750.0,
            fx_rate=32.5,
            currency="USD",
        )

        self.assertEqual(payload["purchase_date"], "2024-01-01")
        self.assertEqual(payload["grams"], 3.0)
        self.assertEqual(payload["cost_usd"], 225750.0)
        self.assertEqual(payload["cost_try"], 7336875.0)


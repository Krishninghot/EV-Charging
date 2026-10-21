import sys, os, unittest; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from scheduler import *
ok = dict(id="A", capacity_kwh=60, soc=.3, arrival_h=0, departure_h=4, min_energy_kwh=10, target_energy_kwh=20, max_kw=50, trust="verified")
class T(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(validate(ok)[0], [])
        for k, v in [("soc", 1.5), ("departure_h", 0), ("target_energy_kwh", 5), ("target_energy_kwh", 999), ("capacity_kwh", -1)]:
            self.assertTrue(validate({**ok, k: v})[0], k)
        self.assertTrue(any("infeasible" in f for f in validate({**ok, "departure_h": .1})[1]))
    def test_scoring_trust(self):
        c = DEFAULT_CFG; a = EV(**{**ok, "trust": "verified"}); b = EV(**{**ok, "trust": "claimed"})
        self.assertGreater(score(a, 0, c, 0)[0], score(b, 0, c, 0)[0])
        self.assertTrue(0 <= score(a, 0, c, 99)[0] <= 100)
    def test_min_need_and_constraints(self):
        r = simulate(SEEDS["balanced"])
        self.assertTrue(all(x["min_met"] for x in r["evs"]))
        for s in r["timeline"]: self.assertLessEqual(s["used_kw"], s["station_kw"] + 1e-6)
        for x in r["evs"]: self.assertLessEqual(x["delivered_kwh"], 75)
    def test_infeasible_reported(self):
        r = simulate(SEEDS["infeasible"]); st = {x["id"]: x["status"] for x in r["evs"]}
        self.assertEqual(st["EV-301"], "infeasible"); self.assertTrue(r["evs"][1]["min_met"])
    def test_power_reduction_reschedule(self):
        r = simulate(SEEDS["overloaded"], events=[dict(t=1.0, type="power_reduction", factor=.5)])
        self.assertTrue(r["events"]); self.assertTrue(all(s["used_kw"] <= s["station_kw"] + 1e-6 for s in r["timeline"]))
        self.assertEqual(r["timeline"][-1]["station_kw"], 50)
    def test_charger_failure(self):
        r = simulate(SEEDS["overloaded"], events=[dict(t=0.5, type="charger_failure", count=2)])
        late = [s for s in r["timeline"] if s["t"] >= .5]; self.assertTrue(all(sum(p > 0 for p in s["alloc"].values()) <= 2 for s in late))
    def test_unsafe_plan_rejected(self):
        r = simulate(SEEDS["balanced"], sabotage=True); self.assertTrue(r["safety_rejections"])
        self.assertTrue(all(s["used_kw"] <= s["station_kw"] + 1e-6 for s in r["timeline"]))
    def test_benchmark_consistency(self):
        a = compare(SEEDS["overloaded"]); b = compare(SEEDS["overloaded"]); self.assertEqual(a, b)
        self.assertEqual(set(a), {"TAFCS", "FCFS", "EDF"})
        for x in a.values(): self.assertLessEqual(x["metrics"]["utilization_pct"], 100)
if __name__ == "__main__": unittest.main()

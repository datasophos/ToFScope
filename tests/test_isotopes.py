"""Exact isotope candidates retain ambiguity and attributed abundance ranges."""
import unittest
from dataclasses import asdict
from isotopes import IsotopeRecord,ion_mz,find_candidates,load_catalog,ELECTRON_MASS_U


class IsotopeTests(unittest.TestCase):
    def setUp(self):
        self.catalog=(IsotopeRecord('A',10,10.,.2,.3,'fixture'),IsotopeRecord('B',10,10.,None,None,'fixture'),IsotopeRecord('A',12,12.,.7,.8,'fixture'))

    def test_charge_mass_and_ties(self):
        # CODATA2022 electron mass5.485799090441e-4u; neutral fixture mass10u.
        self.assertAlmostEqual(ion_mz(self.catalog[0],1),9.999451420090956,places=13)
        self.assertAlmostEqual(ion_mz(self.catalog[0],-1),10.000548579909044,places=13)
        self.assertAlmostEqual(ion_mz(self.catalog[0],2),4.999451420090956,places=13)
        rows=find_candidates(10.,.001,'Th',(1,),self.catalog)
        self.assertEqual([r.isotope.symbol for r in rows],['A','B'])
        self.assertEqual(rows[0].charge,1);self.assertGreater(rows[0].error_Th,0)
        self.assertEqual(asdict(rows[0])['isotope']['abundance_low'],.2)
        self.assertIsNone(rows[1].isotope.abundance_low)

    def test_ppm_boundaries_and_validation(self):
        predicted=ion_mz(self.catalog[0],1)
        self.assertEqual(len(find_candidates(predicted+.001,.00100000001,'Th',(1,),self.catalog)),2)
        self.assertEqual(find_candidates(predicted+.001,10,'ppm',(1,),self.catalog),[])
        self.assertEqual(len(find_candidates(predicted+.001,101,'ppm',(1,),self.catalog)),2)
        for args in [(0,1,'Th',(1,)),(1,-1,'Th',(1,)),(1,float('nan'),'Th',(1,)),(1,1,'x',(1,)),(1,1,'Th',(0,)),(1,1,'Th',(4,)),(1,1,'Th',(True,))]:
            with self.assertRaises(ValueError):find_candidates(*args,self.catalog)

    def test_offline_reference_known_elements_and_ranges(self):
        rows=load_catalog();lookup={(r.symbol,r.mass_number):r for r in rows}
        # NIST saved table neutral masses, CIAAW2024 abundance values.
        self.assertAlmostEqual(lookup['Al',27].neutral_mass_u,26.98153853,places=8)
        self.assertEqual((lookup['Al',27].abundance_low,lookup['Al',27].abundance_high),(1.,1.))
        self.assertAlmostEqual(lookup['Ti',48].neutral_mass_u,47.94794198,places=7)
        self.assertEqual(lookup['Ti',48].abundance_low,.7372)
        self.assertEqual((lookup['C',12].abundance_low,lookup['C',12].abundance_high),(.9884,.9904))
        self.assertIsNone(lookup['C',14].abundance_low)
        self.assertGreater(len(rows),300)


from unittest import SkipTest
import traceback
import tempfile
import unittest
import logging
import shutil
import json
import os.path as op
import os

from pbcommand.models.report import PbReportError
from pbcommand.pb_io.report import dict_to_report
import pbcommand.testkit
from pbcore.util.Process import backticks
from pbcore.io import ReferenceSet
import pbcore.data

from pbreports.report.top_variants import (make_topvariants_report, VariantFinder,
                                           MinorVariantTableBuilder, VariantTableBuilder)

from base_test_case import _get_root_data_dir, run_backticks, \
    skip_if_data_dir_not_present, LOCAL_DATA

log = logging.getLogger(__name__)


class TestTopVariantsReport(unittest.TestCase):
    CONTIG_ID = "lambda_NEB3011"
    DATA_DIR = op.join(LOCAL_DATA, "topvariants")
    REFERENCE = pbcore.data.getLambdaFasta()
    VARIANTS_GFF = op.join(LOCAL_DATA, "variants", "variants.gff.gz")
    RARE_VARIANTS_GFF = op.join(DATA_DIR, "rare_variants.gff.gz")
    N_TOP_VARIANTS = 5
    TABLE_ROW_FIRST = [CONTIG_ID, 19183L, "19183delT", 'DEL', 20, 48, "haploid"]
    TABLE_ROW_LAST = [CONTIG_ID, 24872L, "24872_24873insT", "INS", 17, 41,
                      "haploid"]

    def setUp(self):
        """
        Before *every* test
        """
        self._output_dir = tempfile.mkdtemp(suffix="topvariants")

    def tearDown(self):
        """
        After *every* test
        """
        if os.path.exists(self._output_dir):
            shutil.rmtree(self._output_dir)

    def _get_reference_fasta(self):
        return self.REFERENCE

    def test_make_topvariants_report_input_files(self):
        """
        input gff and ref must be non-null and exist
        """
        ref = self.REFERENCE
        gff = self.VARIANTS_GFF

        # test gff
        with self.assertRaises(PbReportError):
            make_topvariants_report(None, ref, 'foo.json', 1, 10, self._output_dir)

        with self.assertRaises(IOError):
            make_topvariants_report('foo', ref, 'foo.json', 1, 10, self._output_dir)

        # test ref
        with self.assertRaises(PbReportError):
            make_topvariants_report(gff, None, 'foo.json', 1, 10, self._output_dir)

        with self.assertRaises(IOError):
            make_topvariants_report(gff, 'foo', 'foo.json', 1, 10, self._output_dir)

    def test_make_topvariants_report_inputs(self):
        """
        in inputs
        """
        ref = self.REFERENCE
        gff = self.VARIANTS_GFF
        # test how_many
        with self.assertRaises(ValueError):
            make_topvariants_report(gff, ref, 'foo.json', None, 10, self._output_dir)

        # test batch size
        with self.assertRaises(ValueError):
            make_topvariants_report(gff, ref, 'foo.json', 1, None, self._output_dir)

    def test_variant_finder(self):
        ref = self.REFERENCE
        gff = self.VARIANTS_GFF
        vf = VariantFinder(gff, ref, 100, 10000)
        top = vf.find_top()
        self.assertEqual(self.N_TOP_VARIANTS, len(top))

    def test_variant_table_builder(self):
        """
        Test the length and values of a table produced by the standard variant table builder
        """
        tb = VariantTableBuilder()
        columns = tb.table.columns

        self.assertEqual('top_variants_table', tb.table.id)

        self.assertEqual(7, len(columns))
        self.assertEqual('Sequence', columns[0].header)
        self.assertEqual('Position', columns[1].header)
        self.assertEqual('Variant', columns[2].header)
        self.assertEqual('Type', columns[3].header)
        self.assertEqual('Coverage', columns[4].header)
        self.assertEqual('Confidence', columns[5].header)
        self.assertEqual('Genotype', columns[6].header)

        ref = self.REFERENCE
        gff = self.VARIANTS_GFF
        vf = VariantFinder(gff, ref, 100, 10000)
        top = vf.find_top()

        for v in top:
            tb.add_variant(v)

        columns = tb.table.columns

        # This tests the first row
        for i in range(7):
            self.assertEqual(self.TABLE_ROW_FIRST[i], columns[i].values[0])

        for i in range(7):
            self.assertEqual(self.TABLE_ROW_LAST[i], columns[i].values[-1])

    def test_minor_variant_table_builder(self):
        """
        Test the length and values of a table produced by the minor variant table builder
        """
        tb = MinorVariantTableBuilder()

        self.assertEqual('top_minor_variants_table', tb.table.id)

        columns = tb.table.columns
        self.assertEqual(7, len(columns))
        self.assertEqual('Sequence', columns[0].header)
        self.assertEqual('Position', columns[1].header)
        self.assertEqual('Variant', columns[2].header)
        self.assertEqual('Type', columns[3].header)
#        self.assertEqual('Frequency', columns[4].header)
        self.assertEqual('Coverage', columns[4].header)
        self.assertEqual('Confidence', columns[5].header)
        self.assertEqual('Frequency', columns[6].header)

        ref = self.REFERENCE
        gff = self.RARE_VARIANTS_GFF
        vf = VariantFinder(gff, ref, 100, 10000)
        v = vf.find_top()[0]

        tb.add_variant(v)
        columns = tb.table.columns
        self.assertEqual(self.CONTIG_ID, columns[0].values[0])
        self.assertEqual(35782L, columns[1].values[0])
        self.assertEqual('35782G>T', columns[2].values[0])
        self.assertEqual('SUB', columns[3].values[0])
        self.assertEqual(742, columns[4].values[0])
        self.assertEqual(7, columns[5].values[0])
        self.assertEqual(9, columns[6].values[0])

    def test_make_topvariants_report(self):
        """
        Call the main report generation method. Deserialize report, check content.
        """
        ref = self.REFERENCE
        gff = self.VARIANTS_GFF
        make_topvariants_report(gff, ref, 100, 10000, 'rpt.json', self._output_dir)

        # deserialize report
        s = None
        with open(os.path.join(self._output_dir, 'rpt.json'), 'r') as f:
            s = json.load(f)

        report = dict_to_report(s)
        self.assertEqual('Genotype', report.tables[0].columns[6].header)

    def test_make_minor_topvariants_report(self):
        """
        Call the main report generation method with minor kwarg==True. Deserialize report, check content.
        """
        ref = self.REFERENCE
        gff = self.RARE_VARIANTS_GFF
        make_topvariants_report(gff, ref, 100, 10000, 'rpt.json', self._output_dir, is_minor_variants_rpt=True)

        # deserialize report
        s = None
        with open(os.path.join(self._output_dir, 'rpt.json'), 'r') as f:
            s = json.load(f)

        report = dict_to_report(s)
        self.assertEqual('Frequency', report.tables[0].columns[6].header)

    def test_exit_code_0(self):
        """
        Like a cram test. Assert exits with 0.
        """
        ref = self.REFERENCE
        gff = self.VARIANTS_GFF
        j = 'rpt.json'
        cmd = 'python -m pbreports.report.top_variants {o} {j} {g} {r}'.format(
            o=self._output_dir, g=gff, r=ref, j=j)
        log.info(cmd)
        rcode = run_backticks(cmd)
        self.assertEquals(0, rcode)
        self.assertTrue(os.path.exists(os.path.join(self._output_dir, j)))

    def test_exit_code_0_referenceset(self):
        """
        Like a cram test. Assert exits with 0 with ReferenceSet XML
        """
        ref = self._get_reference_fasta()
        ref_name = os.path.join(self._output_dir, "refset.xml")
        refset = ReferenceSet(ref)
        refset.write(ref_name)
        ref = ref_name
        j = 'rpt.json'
        cmd = 'python -m pbreports.report.top_variants {o} {j} {g} {r}'.format(
            o=self._output_dir,
            g=self.VARIANTS_GFF, r=ref, j=j)
        log.info(cmd)

        rcode = run_backticks(cmd)
        self.assertEquals(0, rcode)
        self.assertTrue(os.path.exists(os.path.join(self._output_dir, j)))

    def test_exit_code_0_top_corrections(self):
        """
        Like a cram test. Assert exits with 0. This creates the 'top corrections' report,
        which is exactly the same as the top variants reports, except that table
        columns in the smrtportal have been renamed. This is accomplished via the rules.
        """
        ref = self.REFERENCE
        gff = self.VARIANTS_GFF
        cmd = 'python -m pbreports.report.top_variants {o} rpt.json {g} {r}'.format(o=self._output_dir, g=self.VARIANTS_GFF, r=ref)
        log.info(cmd)
        o, c, m = backticks(cmd)

        if c is not 0:
            log.error(m)
            log.error(o)
            print(m)
        self.assertEquals(0, c)
        self.assertTrue(os.path.exists(os.path.join(self._output_dir, 'rpt.json')))

    @unittest.skip("TEMPORARILY DISABLED")
    def test_exit_code_0_minor(self):
        """
        Like a cram test. Create the minor report in a subprocess. Assert that the report is correct.
        """
        ref = self.REFERENCE
        gff = self.RARE_VARIANTS_GFF
        cmd = 'pbreport minor-topvariants {o} rpt.json {g} {r}'.format(o=self._output_dir,
                                                                          g=gff, r=ref)
        log.info(cmd)
        o, c, m = backticks(cmd)
        if c is not 0:
            log.error(m)
            log.error(o)
            print(m)
        self.assertEquals(0, c)
        # deserialize report
        s = None
        with open(os.path.join(self._output_dir, 'rpt.json'), 'r') as f:
            s = json.load(f)

        report = dict_to_report(s)
        self.assertEqual('Frequency', report.tables[0].columns[6].header)


@skip_if_data_dir_not_present
class TestTopVariantsReportEcoli(TestTopVariantsReport):
    CONTIG_ID = "ecoliK12_pbi_March2013"
    DATA_DIR = op.join(_get_root_data_dir(), "topvariants")
    REFERENCE = op.join(DATA_DIR, CONTIG_ID)
    VARIANTS_GFF = op.join(DATA_DIR, "variants.gff.gz")
    RARE_VARIANTS_GFF = op.join(DATA_DIR, "rare_variants.gff.gz")
    N_TOP_VARIANTS = 9
    TABLE_ROW_FIRST = [
        CONTIG_ID,
        1849183L,
        '1849183_1849184insT',
        'INS',
        20,
        48,
        'haploid',
    ]
    TABLE_ROW_LAST = [
        CONTIG_ID,
        3785544L,
        '3785544_3785545insA',
        'INS',
        18,
        40,
        'haploid',
    ]

    def _get_reference_fasta(self):
        return op.join(self.REFERENCE, "sequence",
                       "ecoliK12_pbi_March2013.fasta")

    def test_exit_code_0_fasta(self):
        """
        Like a cram test. Assert exits with 0 with fasta
        """
        ref = self._get_reference_fasta()
        gff = self.VARIANTS_GFF
        j = 'rpt.json'
        cmd = 'python -m pbreports.report.top_variants {o} {j} {g} {r}'.format(o=self._output_dir,
                                                                    g=gff, r=ref, j=j)
        log.info(cmd)

        rcode = run_backticks(cmd)
        self.assertEquals(0, rcode)
        self.assertTrue(os.path.exists(os.path.join(self._output_dir, j)))

    def test_minor_variant_table_builder(self):
        raise SkipTest("IGNORE")


class TestPbreportTopVariants(pbcommand.testkit.PbTestApp):
    from pbreports.report.top_variants import Constants
    DRIVER_BASE = "python -m pbreports.report.top_variants "
    DRIVER_EMIT = DRIVER_BASE + " --emit-tool-contract "
    DRIVER_RESOLVE = DRIVER_BASE + " --resolved-tool-contract "
    REQUIRES_PBCORE = True
    INPUT_FILES = [
        os.path.join(LOCAL_DATA, "variants", "variants.gff.gz"),
        pbcore.data.getLambdaFasta(),
    ]
    TASK_OPTIONS = {
        Constants.HOW_MANY_ID: Constants.HOW_MANY_DEFAULT,
        Constants.BATCH_SORT_SIZE_ID: Constants.BATCH_SORT_SIZE_DEFAULT,
    }

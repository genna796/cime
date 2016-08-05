"""
Base class for CIME system tests that involve doing two runs and comparing their
output.

In the __init__ method for your test, you MUST call
    SystemTestsCompareTwoClone.__init__
See the documentation of that method for details.

Classes that inherit from this are REQUIRED to implement the following methods:

(1) _common_setup
    This method will be called to set up both cases. It should contain any setup
    that's needed in both cases. This is called before _case_one_setup or
    _case_two_setup.

(2) _case_one_setup
    This method will be called to set up case 1, the "base" case

(3) _case_two_setup
    This method will be called to set up case 2, the "test" case
"""

from CIME.XML.standard_module_setup import *
from CIME.SystemTests.system_tests_common import SystemTestsCommon

import shutil, os

logger = logging.getLogger(__name__)

class SystemTestsCompareTwoClone(SystemTestsCommon):

    def __init__(self,
                 case,
                 run_two_suffix = 'test',
                 run_one_description = '',
                 run_two_description = ''):
        """
        Initialize a SystemTestsCompareTwoClone object. Individual test cases that
        inherit from SystemTestsCompareTwoClone MUST call this __init__ method.

        Args:
            case: case object passsed to __init__ method of individual test
            run_two_suffix (str, optional): Suffix appended to the case name for
                the second run. Defaults to 'test'. This can be anything other
                than 'base'.
            run_one_description (str, optional): Description printed to log file
                when starting the first run. Defaults to ''.
            run_two_description (str, optional): Description printed to log file
                when starting the second run. Defaults to ''.
        """
        SystemTestsCommon.__init__(self, case)

        # run_one_suffix is just used as the suffix for the netcdf files
        # produced by the first case; we may eventually remove this, but for now
        # it is needed by the various component_*.sh scripts. run_two_suffix is
        # also used as the suffix for netcdf files, but more importantly is used
        # to create the case name for the clone case.
        #
        # NOTE(wjs, 2016-08-03) It is currently CRITICAL for run_one_suffix to
        # be 'base', because this is assumed for baseline comparison and
        # generation. Once that assumption is relaxed, then run_one_suffix can
        # be set in the call to the constructor just like run_two_suffix
        # currently is. Or, if these tools are rewritten to work without any
        # suffix, then run_one_suffix can be removed entirely.
        self._run_one_suffix = 'base'
        self._run_two_suffix = run_two_suffix.rstrip()
        expect(self._run_two_suffix != self._run_one_suffix,
               "ERROR: Must have different suffixes for run one and run two")

        self._run_one_description = run_one_description
        self._run_two_description = run_two_description

        # Initialize test results
        # TODO(wjs, 2016-07-27) Currently these results of the individual pieces
        # aren't used anywhere, but I'm storing them because I think it would be
        # helpful to use them in the test reporting
        self._status_run1 = "NOT RUN"
        self._status_run2 = "NOT RUN"
        self._status_compare = "NOT RUN"

        # Save case for first run so we can return to it if we switch self._case
        # to point to self._case2
        self._case1 = self._case
        self._caseroot1 = self._get_caseroot()

        # Determine if case2 already exists on disk. If it does, create a _case2
        # object that points to the case directory. If it doesn't, create it.
        #
        # We also use the existence of the case2 directory to signal whether we
        # have done the necessary test setup for this test: When we initially
        # create the case2 directory, we set up both test cases; then, if we
        # find that the case2 directory already exists, we assume that the setup
        # has already been done. (In some cases it could be problematic to redo
        # the test setup when it's not needed - e.g., by appending things to
        # user_nl files multiple times. This is why we want to make sure to just
        # do the test setup once.)
        self._caseroot2 = self._get_caseroot2()
        if os.path.exists(self._caseroot2):
            self._case2 = Case(case_root=self._caseroot2, read_only=False)
        else:
            try:
                # TODO(wjs, 2016-08-05) For now, we're hard-coding keepexe=True; in
                # the future, make this set-able via an argument to the constructor.
                self._case2 = self._case1.create_clone(
                    newcase = self._caseroot2,
                    keepexe = True)
                self._setup_cases()
            except:
                # If a problem occurred in setting up the test cases, it's
                # important to blow away the case2 directory: If it's kept
                # around, that would signal that test setup was done
                # successfully, and thus doesn't need to be redone - which is
                # not the case. Of course, we'll likely be left in an
                # inconsistent state in this case, but if we didn't blow away
                # the case2 directory, the next re-build of the test would
                # think, "okay, setup is done, I can move on to the build",
                # which would be wrong.
                shutil.rmtree(self._caseroot2)
                raise

    # ========================================================================
    # Methods that MUST be implemented by specific tests that inherit from this
    # base class
    # ========================================================================

    def _common_setup(self):
        """
        This method will be called to set up both cases. It should contain any setup
        that's needed in both cases. This is called before _case_one_setup or
        _case_two_setup.

        This should be written to refer to self._case: It will be called once with
        self._case pointing to case1, and once with self._case pointing to case2.
        """
        raise NotImplementedError

    def _case_one_setup(self):
        """
        This method will be called to set up case 1, the "base" case.

        This should be written to refer to self._case: this object will point to
        case1 at the point that this is called.
        """
        raise NotImplementedError

    def _case_two_setup(self):
        """
        This method will be called to set up case 2, the "test" case

        This should be written to refer to self._case: this object will point to
        case2 at the point that this is called.
        """
        raise NotImplementedError

    # ========================================================================
    # Main public methods
    # ========================================================================

    def build(self, sharedlib_only=False, model_only=False):
        # TODO(wjs, 2016-08-05) This currently assumes that the two cases use
        # the same build. Once we relax that assumption, we'll need a
        # conditional here: If the two cases use the same build (set by an
        # argument to the __init__ method), then use the below logic; otherwise,
        # do two builds.
        self._activate_case1()
        SystemTestsCommon.build(self, sharedlib_only=sharedlib_only, model_only=model_only)

    def run(self):
        """
        Runs both phases of the two-phase test and compares their results
        """

        # First run
        logger.info('Doing first run: ' + self._run_one_description)
        self._activate_case1()
        success = self._run(self._run_one_suffix)
        if success:
            self._status_run1 = "PASS"
        else:
            self._status_run1 = "FAIL"
            return False

        # Second run
        logger.info('Doing second run: ' + self._run_two_description)
        self._activate_case2()
        success = self._run(self._run_two_suffix)
        if success:
            self._status_run2 = "PASS"
        else:
            self._status_run2 = "FAIL"
            return False

        # FIXME(wjs, 2016-08-05) Call a function to make sym links from the
        # case1 run directory pointing to the files in the case2 run directory

        # Compare results
        # Case1 is the "main" case, and we need to do the comparisons from there
        self._activate_case1()
        success = self._component_compare_test(self._run_one_suffix, self._run_two_suffix)
        if success:
            self._status_compare = "PASS"
        else:
            self._status_compare = "FAIL"
            return False

        return success

    def get_run_one_status(self):
        """
        Returns a string specifying the status of run 1
        """
        return self._status_run1

    def get_run_two_status(self):
        """
        Returns a string specifying the status of run 2
        """
        return self._status_run2

    def get_compare_status(self):
        """
        Returns a string specifying the status of the comparison between run 1
        and run 2
        """
        return self._status_compare

    # ========================================================================
    # Private methods
    # ========================================================================

    def _get_caseroot2(self):
        """
        Determines and returns caseroot for case2

        Assumes that self._case1 is already set to point to the case1 object,
        and that self._run_two_suffix is already set.
        """
        casename1 = self._case1.get_value("CASE")
        caseroot1 = self._case1.get_value("CASEROOT")

        casename2 = "%s.%s"%(casename1, self._run_two_suffix)

        # Nest the case directory for case2 inside the case directory for case1
        caseroot2 = os.path.join(caseroot1, casename2)

        return caseroot2

    def _setup_cases(self):
        """
        Does all test-specific set up for the two test cases.
        """

        # Set up case 1
        self._activate_case1()
        self._common_setup()
        self._case_one_setup()

        # Set up case 2
        self._activate_case2()
        self._common_setup()
        self._case_two_setup()
        # Flush the case so that, if errors occur later, then at least case2 is
        # in a correct, post-setup state
        self._case.flush()

        # Flush case 1. We do this at the end rather than immediately after
        # setting up case 1 so that, if an exception is raised in the set up for
        # case 2, then case 1 will be in its original (pre-setup) state.
        self._activate_case1()
        self._case.flush()

    def _activate_case1(self):
        """
        Make case 1 active for upcoming calls
        """
        os.chdir(self._caseroot1)
        self._set_active_case(self._case1)

    def _activate_case2(self):
        """
        Make case 2 active for upcoming calls
        """
        os.chdir(self._caseroot2)
        self._set_active_case(self._case2)

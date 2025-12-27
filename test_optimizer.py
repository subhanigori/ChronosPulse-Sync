#!/usr/bin/env python3
"""
Unit Tests for NTP Server Optimizer - Enterprise Edition

Author: subhanigori@gmail.com
Version: 2.0.0
Copyright (c) 2024 subhanigori@gmail.com

Comprehensive test suite for NTP optimizer functionality
"""

import unittest
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ntp_optimizer import NTPOptimizer, NTPServer, CONFIG
except ImportError:
    print("ERROR: Could not import ntp_optimizer module")
    print("Make sure ntp_optimizer.py is in the same directory")
    sys.exit(1)


class TestNTPServerDataClass(unittest.TestCase):
    """Test NTPServer data class functionality"""
    
    def test_server_creation_with_defaults(self):
        """Test creating NTPServer with default values"""
        server = NTPServer(hostname="time.example.com")
        self.assertEqual(server.hostname, "time.example.com")
        self.assertEqual(server.offset, 999.0)
        self.assertEqual(server.jitter, 999.0)
        self.assertEqual(server.stratum, 16)
        self.assertEqual(server.reachability, 0.0)
        self.assertEqual(server.score, 0.0)
        self.assertFalse(server.tested)
    
    def test_server_creation_with_values(self):
        """Test creating NTPServer with specific values"""
        server = NTPServer(
            hostname="time.cloudflare.com",
            offset=1.5,
            jitter=0.3,
            stratum=2,
            reachability=95.0,
            score=92.5,
            tested=True,
            region="global"
        )
        
        self.assertEqual(server.hostname, "time.cloudflare.com")
        self.assertEqual(server.offset, 1.5)
        self.assertEqual(server.jitter, 0.3)
        self.assertEqual(server.stratum, 2)
        self.assertEqual(server.reachability, 95.0)
        self.assertEqual(server.score, 92.5)
        self.assertTrue(server.tested)
        self.assertEqual(server.region, "global")
    
    def test_to_dict_conversion(self):
        """Test conversion to dictionary"""
        server = NTPServer(
            hostname="test.com",
            offset=2.0,
            stratum=3
        )
        d = server.to_dict()
        
        self.assertIsInstance(d, dict)
        self.assertIn('hostname', d)
        self.assertIn('offset', d)
        self.assertIn('stratum', d)
        self.assertEqual(d['hostname'], 'test.com')
        self.assertEqual(d['offset'], 2.0)
        self.assertEqual(d['stratum'], 3)


class TestConfigurationValidation(unittest.TestCase):
    """Test configuration validation and defaults"""
    
    def test_config_structure(self):
        """Test CONFIG has required sections"""
        required_sections = ['testing', 'selection', 'logging', 'server_sources', 
                           'geographic', 'notifications', 'advanced']
        for section in required_sections:
            self.assertIn(section, CONFIG)
    
    def test_weights_sum_to_one(self):
        """Test that selection weights sum to approximately 1.0"""
        weights = CONFIG['selection']
        total = (
            weights['weight_latency'] +
            weights['weight_jitter'] +
            weights['weight_stratum'] +
            weights['weight_reachability']
        )
        self.assertAlmostEqual(total, 1.0, places=2, 
                              msg="Selection weights must sum to 1.0")
    
    def test_reliability_priority(self):
        """Test that weights prioritize reliability & accuracy over speed"""
        weights = CONFIG['selection']
        
        # Jitter + Reachability (reliability) should be > 50%
        reliability_weight = weights['weight_jitter'] + weights['weight_reachability']
        self.assertGreater(reliability_weight, 0.5, 
                          "Reliability weights should exceed 50%")
        
        # Latency (speed) should be lowest weight
        self.assertLess(weights['weight_latency'], 0.15,
                       "Latency weight should be minimal for client servers")
        
        # Stratum (accuracy) should be significant
        self.assertGreater(weights['weight_stratum'], 0.15,
                          "Stratum weight should be significant for accuracy")
    
    def test_testing_configuration(self):
        """Test testing configuration has reasonable values"""
        testing = CONFIG['testing']
        
        self.assertGreater(testing['samples_per_server'], 0)
        self.assertGreater(testing['timeout'], 0)
        self.assertGreater(testing['interval_hours'], 0)
        self.assertGreater(testing['max_servers_to_test'], 0)
        
        # Reasonable ranges
        self.assertLessEqual(testing['samples_per_server'], 10)
        self.assertLessEqual(testing['timeout'], 30)


class TestNTPOptimizerInitialization(unittest.TestCase):
    """Test NTPOptimizer initialization"""
    
    def setUp(self):
        """Create temporary directory for test files"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
    
    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_initialization_dry_run(self):
        """Test optimizer initialization in dry-run mode"""
        optimizer = NTPOptimizer(dry_run=True)
        
        self.assertTrue(optimizer.dry_run)
        self.assertIsNotNone(optimizer.config)
        self.assertIsNotNone(optimizer.logger)
        self.assertTrue(optimizer.log_dir.exists())
        self.assertTrue(optimizer.data_dir.exists())
    
    def test_initialization_with_custom_config(self):
        """Test initialization with custom configuration"""
        custom_config = CONFIG.copy()
        custom_config['testing']['interval_hours'] = 12
        
        optimizer = NTPOptimizer(config=custom_config, dry_run=True)
        
        self.assertEqual(optimizer.config['testing']['interval_hours'], 12)
    
    def test_directory_creation(self):
        """Test that logs and data directories are created"""
        optimizer = NTPOptimizer(dry_run=True)
        
        self.assertTrue((Path.cwd() / "logs").exists())
        self.assertTrue((Path.cwd() / "data").exists())


class TestScoreCalculation(unittest.TestCase):
    """Test NTP server score calculation algorithm"""
    
    def setUp(self):
        """Create optimizer instance for testing"""
        self.optimizer = NTPOptimizer(dry_run=True)
    
    def test_perfect_server_score(self):
        """Test score for ideal server"""
        perfect = NTPServer(
            hostname="perfect.com",
            offset=0.1,      # Very low latency
            jitter=0.05,     # Very stable
            stratum=1,       # Atomic clock direct
            reachability=100.0  # Always available
        )
        
        score = self.optimizer.calculate_score(perfect)
        
        self.assertGreater(score, 90, "Perfect server should score >90")
        self.assertLessEqual(score, 100, "Score cannot exceed 100")
    
    def test_poor_server_score(self):
        """Test score for poor server"""
        poor = NTPServer(
            hostname="poor.com",
            offset=50.0,     # High latency
            jitter=20.0,     # Very unstable
            stratum=4,       # Far from reference
            reachability=60.0  # Unreliable
        )
        
        score = self.optimizer.calculate_score(poor)
        
        self.assertLess(score, 50, "Poor server should score <50")
    
    def test_score_comparison(self):
        """Test that better servers score higher"""
        good = NTPServer(
            hostname="good.com",
            offset=2.0,
            jitter=0.5,
            stratum=2,
            reachability=95.0
        )
        
        mediocre = NTPServer(
            hostname="mediocre.com",
            offset=10.0,
            jitter=5.0,
            stratum=3,
            reachability=80.0
        )
        
        good_score = self.optimizer.calculate_score(good)
        mediocre_score = self.optimizer.calculate_score(mediocre)
        
        self.assertGreater(good_score, mediocre_score,
                          "Better server should score higher")
    
    def test_reliability_vs_speed(self):
        """Test that reliability is prioritized over speed"""
        fast_unreliable = NTPServer(
            hostname="fast.com",
            offset=0.5,      # Very fast
            jitter=15.0,     # But unstable
            stratum=2,
            reachability=70.0  # And unreliable
        )
        
        slow_reliable = NTPServer(
            hostname="reliable.com",
            offset=10.0,     # Slower
            jitter=0.5,      # But stable
            stratum=2,
            reachability=100.0  # And reliable
        )
        
        fast_score = self.optimizer.calculate_score(fast_unreliable)
        reliable_score = self.optimizer.calculate_score(slow_reliable)
        
        self.assertGreater(reliable_score, fast_score,
                          "Reliable server should score higher than fast but unreliable")
    
    def test_regional_bonus(self):
        """Test regional server bonus"""
        self.optimizer.detected_continent = "asia"
        
        regional = NTPServer(
            hostname="0.asia.pool.ntp.org",
            offset=5.0,
            jitter=1.0,
            stratum=2,
            reachability=95.0,
            region="asia"
        )
        
        global_server = NTPServer(
            hostname="pool.ntp.org",
            offset=5.0,
            jitter=1.0,
            stratum=2,
            reachability=95.0,
            region="global"
        )
        
        regional_score = self.optimizer.calculate_score(regional)
        global_score = self.optimizer.calculate_score(global_server)
        
        # Regional should get a small bonus
        self.assertGreaterEqual(regional_score, global_score)


class TestServerSorting(unittest.TestCase):
    """Test server sorting and selection logic"""
    
    def test_sort_by_score(self):
        """Test that servers are sorted by score correctly"""
        servers = [
            NTPServer(hostname="server1.com", score=75.0),
            NTPServer(hostname="server2.com", score=95.0),
            NTPServer(hostname="server3.com", score=85.0),
            NTPServer(hostname="server4.com", score=90.0),
        ]
        
        servers.sort(key=lambda x: x.score, reverse=True)
        
        self.assertEqual(servers[0].hostname, "server2.com")  # 95.0
        self.assertEqual(servers[1].hostname, "server4.com")  # 90.0
        self.assertEqual(servers[2].hostname, "server3.com")  # 85.0
        self.assertEqual(servers[3].hostname, "server1.com")  # 75.0
    
    def test_best_server_selection(self):
        """Test selecting the best server"""
        servers = [
            NTPServer(hostname="server1.com", score=75.0),
            NTPServer(hostname="server2.com", score=95.0),
            NTPServer(hostname="server3.com", score=85.0),
        ]
        
        servers.sort(key=lambda x: x.score, reverse=True)
        best = servers[0]
        
        self.assertEqual(best.hostname, "server2.com")
        self.assertEqual(best.score, 95.0)


class TestGeographicDetection(unittest.TestCase):
    """Test geographic region detection"""
    
    def setUp(self):
        """Create optimizer instance"""
        self.optimizer = NTPOptimizer(dry_run=True)
    
    @patch('subprocess.run')
    def test_timezone_detection(self, mock_run):
        """Test timezone detection from timedatectl"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Timezone=Asia/Kolkata"
        )
        
        continent, region = self.optimizer.detect_geographic_region()
        
        self.assertEqual(continent, "asia")
    
    @patch('subprocess.run')
    def test_timezone_parsing(self, mock_run):
        """Test parsing different timezone formats"""
        test_cases = [
            ("Asia/Tokyo", "asia"),
            ("Europe/London", "europe"),
            ("America/New_York", "north-america"),
            ("Africa/Cairo", "africa"),
            ("Australia/Sydney", "oceania"),
        ]
        
        for timezone, expected_region in test_cases:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=f"Timezone={timezone}"
            )
            
            continent, region = self.optimizer.detect_geographic_region()
            
            self.assertEqual(continent, expected_region,
                           f"Failed for timezone {timezone}")


class TestBlacklistManagement(unittest.TestCase):
    """Test server blacklisting functionality"""
    
    def setUp(self):
        """Create temporary directory and optimizer"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        self.optimizer = NTPOptimizer(dry_run=True)
    
    def tearDown(self):
        """Clean up"""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_blacklist_initialization(self):
        """Test blacklist starts empty"""
        self.assertEqual(len(self.optimizer.blacklist), 0)
    
    def test_add_to_blacklist(self):
        """Test adding servers to blacklist"""
        self.optimizer.blacklist.add("bad.server.com")
        self.assertIn("bad.server.com", self.optimizer.blacklist)
    
    def test_blacklist_persistence(self):
        """Test blacklist is saved and loaded"""
        self.optimizer.blacklist.add("failed.server.com")
        self.optimizer._save_blacklist()
        
        # Create new optimizer instance
        new_optimizer = NTPOptimizer(dry_run=True)
        
        self.assertIn("failed.server.com", new_optimizer.blacklist)


class TestConfigurationEditing(unittest.TestCase):
    """Test configuration modification scenarios"""
    
    def test_interval_override(self):
        """Test command-line interval override"""
        custom_config = CONFIG.copy()
        custom_config['testing']['interval_hours'] = 12
        
        optimizer = NTPOptimizer(config=custom_config, dry_run=True)
        
        self.assertEqual(optimizer.config['testing']['interval_hours'], 12)
    
    def test_weight_modification(self):
        """Test modifying selection weights"""
        custom_config = CONFIG.copy()
        custom_config['selection']['weight_jitter'] = 0.5
        custom_config['selection']['weight_reachability'] = 0.3
        custom_config['selection']['weight_stratum'] = 0.15
        custom_config['selection']['weight_latency'] = 0.05
        
        optimizer = NTPOptimizer(config=custom_config, dry_run=True)
        
        # Verify weights are updated
        self.assertEqual(optimizer.config['selection']['weight_jitter'], 0.5)
        
        # Verify they still sum to 1.0
        total = sum([
            optimizer.config['selection']['weight_jitter'],
            optimizer.config['selection']['weight_reachability'],
            optimizer.config['selection']['weight_stratum'],
            optimizer.config['selection']['weight_latency']
        ])
        self.assertAlmostEqual(total, 1.0, places=2)


class TestPerformanceHistory(unittest.TestCase):
    """Test performance history tracking"""
    
    def setUp(self):
        """Create temporary directory and optimizer"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        self.optimizer = NTPOptimizer(dry_run=True)
    
    def tearDown(self):
        """Clean up"""
        os.chdir(self.original_dir)
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_history_saving(self):
        """Test saving performance history"""
        servers = [
            NTPServer(
                hostname="test1.com",
                offset=1.5,
                jitter=0.3,
                stratum=2,
                reachability=95.0,
                score=90.0
            ),
            NTPServer(
                hostname="test2.com",
                offset=2.0,
                jitter=0.5,
                stratum=3,
                reachability=90.0,
                score=85.0
            )
        ]
        
        self.optimizer.save_performance_history(servers)
        
        history_file = Path("data/server_history.json")
        self.assertTrue(history_file.exists())
        
        with open(history_file) as f:
            history = json.load(f)
        
        self.assertIsInstance(history, list)
        self.assertGreater(len(history), 0)
        self.assertIn('timestamp', history[0])
        self.assertIn('servers', history[0])


def run_test_suite():
    """Run all tests with detailed output"""
    print("=" * 80)
    print("NTP Server Optimizer - Enterprise Edition")
    print("Comprehensive Test Suite")
    print(f"Developer: {__author__}")
    print("=" * 80)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestNTPServerDataClass,
        TestConfigurationValidation,
        TestNTPOptimizerInitialization,
        TestScoreCalculation,
        TestServerSorting,
        TestGeographicDetection,
        TestBlacklistManagement,
        TestConfigurationEditing,
        TestPerformanceHistory,
    ]
    
    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests Run:      {result.testsRun}")
    print(f"Successes:      {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures:       {len(result.failures)}")
    print(f"Errors:         {len(result.errors)}")
    print(f"Success Rate:   {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print("=" * 80)
    print()
    
    if result.wasSuccessful():
        print("✓ ALL TESTS PASSED")
        print(f"Developer: {__author__}")
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(run_test_suite())

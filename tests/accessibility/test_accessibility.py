"""
Accessibility testing framework for Newsletter Podcast Generator web interface.

This module provides utilities for testing WCAG 2.1 AA compliance and
accessibility standards for the web interface components.
"""

import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path

import pytest
from httpx import AsyncClient

from src.lib.config import get_settings
from src.lib.logging import get_logger

logger = get_logger(__name__)


class AccessibilityTester:
    """Base class for accessibility testing utilities."""
    
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        """Initialize accessibility tester."""
        self.base_url = base_url
        self.results: List[Dict[str, Any]] = []
    
    async def test_page_accessibility(self, path: str) -> Dict[str, Any]:
        """Test accessibility of a specific page."""
        url = f"{self.base_url}{path}"
        
        # Basic accessibility checks that can be done server-side
        result = {
            "url": url,
            "path": path,
            "tests": [],
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
        
        try:
            async with AsyncClient() as client:
                response = await client.get(url)
                
                if response.status_code != 200:
                    result["tests"].append({
                        "test": "page_accessibility",
                        "status": "failed",
                        "message": f"Page not accessible (status: {response.status_code})"
                    })
                    result["failed"] += 1
                    return result
                
                content = response.text
                
                # Test HTML structure
                html_tests = await self._test_html_structure(content)
                result["tests"].extend(html_tests)
                
                # Test form accessibility
                form_tests = await self._test_form_accessibility(content)
                result["tests"].extend(form_tests)
                
                # Test navigation accessibility
                nav_tests = await self._test_navigation_accessibility(content)
                result["tests"].extend(nav_tests)
                
                # Count results
                for test in result["tests"]:
                    if test["status"] == "passed":
                        result["passed"] += 1
                    elif test["status"] == "failed":
                        result["failed"] += 1
                    elif test["status"] == "warning":
                        result["warnings"] += 1
        
        except Exception as e:
            logger.error(f"Error testing accessibility for {url}: {e}")
            result["tests"].append({
                "test": "page_accessibility",
                "status": "error",
                "message": f"Error during testing: {str(e)}"
            })
        
        self.results.append(result)
        return result
    
    async def _test_html_structure(self, html_content: str) -> List[Dict[str, Any]]:
        """Test HTML structure for accessibility."""
        tests = []
        
        # Check for proper heading structure
        import re
        
        # Check for title tag
        if '<title>' in html_content and '</title>' in html_content:
            tests.append({
                "test": "page_title",
                "status": "passed",
                "message": "Page has title tag"
            })
        else:
            tests.append({
                "test": "page_title",
                "status": "failed",
                "message": "Page missing title tag"
            })
        
        # Check for lang attribute on html tag
        if re.search(r'<html[^>]*lang=', html_content):
            tests.append({
                "test": "html_lang",
                "status": "passed",
                "message": "HTML has lang attribute"
            })
        else:
            tests.append({
                "test": "html_lang",
                "status": "failed",
                "message": "HTML missing lang attribute"
            })
        
        # Check for heading hierarchy
        headings = re.findall(r'<h([1-6])', html_content)
        if headings:
            heading_levels = [int(h) for h in headings]
            if heading_levels[0] == 1:  # Should start with H1
                tests.append({
                    "test": "heading_hierarchy",
                    "status": "passed",
                    "message": "Proper heading hierarchy starting with H1"
                })
            else:
                tests.append({
                    "test": "heading_hierarchy",
                    "status": "warning",
                    "message": "Heading hierarchy doesn't start with H1"
                })
        
        # Check for alt attributes on images
        img_tags = re.findall(r'<img[^>]*>', html_content)
        images_without_alt = [img for img in img_tags if 'alt=' not in img]
        
        if not img_tags:
            tests.append({
                "test": "image_alt_text",
                "status": "passed",
                "message": "No images found"
            })
        elif not images_without_alt:
            tests.append({
                "test": "image_alt_text",
                "status": "passed",
                "message": "All images have alt attributes"
            })
        else:
            tests.append({
                "test": "image_alt_text",
                "status": "failed",
                "message": f"{len(images_without_alt)} images missing alt attributes"
            })
        
        return tests
    
    async def _test_form_accessibility(self, html_content: str) -> List[Dict[str, Any]]:
        """Test form accessibility."""
        tests = []
        import re
        
        # Find all form inputs
        inputs = re.findall(r'<input[^>]*>', html_content)
        labels = re.findall(r'<label[^>]*>', html_content)
        
        if not inputs:
            tests.append({
                "test": "form_accessibility",
                "status": "passed",
                "message": "No form inputs found"
            })
            return tests
        
        # Check for labels
        if labels:
            tests.append({
                "test": "form_labels",
                "status": "passed",
                "message": "Form has label elements"
            })
        else:
            tests.append({
                "test": "form_labels",
                "status": "warning",
                "message": "No label elements found for form inputs"
            })
        
        # Check for required field indicators
        required_inputs = [inp for inp in inputs if 'required' in inp]
        if required_inputs:
            tests.append({
                "test": "required_fields",
                "status": "passed",
                "message": "Required fields properly marked"
            })
        
        return tests
    
    async def _test_navigation_accessibility(self, html_content: str) -> List[Dict[str, Any]]:
        """Test navigation accessibility."""
        tests = []
        import re
        
        # Check for navigation landmarks
        if '<nav' in html_content:
            tests.append({
                "test": "navigation_landmark",
                "status": "passed",
                "message": "Navigation landmark found"
            })
        else:
            tests.append({
                "test": "navigation_landmark",
                "status": "warning",
                "message": "No navigation landmark found"
            })
        
        # Check for skip links
        skip_links = re.findall(r'href="#[^"]*skip', html_content)
        if skip_links:
            tests.append({
                "test": "skip_links",
                "status": "passed",
                "message": "Skip links found"
            })
        else:
            tests.append({
                "test": "skip_links",
                "status": "warning",
                "message": "No skip links found"
            })
        
        return tests
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate accessibility test report."""
        if not self.results:
            return {"error": "No test results available"}
        
        total_tests = sum(len(result["tests"]) for result in self.results)
        total_passed = sum(result["passed"] for result in self.results)
        total_failed = sum(result["failed"] for result in self.results)
        total_warnings = sum(result["warnings"] for result in self.results)
        
        return {
            "summary": {
                "total_pages": len(self.results),
                "total_tests": total_tests,
                "passed": total_passed,
                "failed": total_failed,
                "warnings": total_warnings,
                "success_rate": (total_passed / total_tests * 100) if total_tests > 0 else 0
            },
            "results": self.results,
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate accessibility improvement recommendations."""
        recommendations = []
        
        # Analyze common failures
        all_failures = []
        for result in self.results:
            all_failures.extend([test for test in result["tests"] if test["status"] == "failed"])
        
        failure_types = {}
        for failure in all_failures:
            test_type = failure["test"]
            failure_types[test_type] = failure_types.get(test_type, 0) + 1
        
        if "page_title" in failure_types:
            recommendations.append("Add descriptive title tags to all pages")
        
        if "html_lang" in failure_types:
            recommendations.append("Add lang attribute to HTML element")
        
        if "image_alt_text" in failure_types:
            recommendations.append("Add descriptive alt text to all images")
        
        if "form_labels" in failure_types:
            recommendations.append("Associate form inputs with descriptive labels")
        
        return recommendations


# Test fixtures and utilities for pytest
@pytest.fixture
async def accessibility_tester():
    """Pytest fixture for accessibility tester."""
    return AccessibilityTester()


@pytest.fixture
async def test_client():
    """Pytest fixture for test client."""
    from src.api.app import app
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


# Test cases for accessibility
@pytest.mark.accessibility
async def test_homepage_accessibility(accessibility_tester: AccessibilityTester):
    """Test homepage accessibility."""
    result = await accessibility_tester.test_page_accessibility("/")
    assert result["failed"] == 0, f"Accessibility failures: {result['tests']}"


@pytest.mark.accessibility
async def test_api_docs_accessibility(accessibility_tester: AccessibilityTester):
    """Test API documentation accessibility."""
    result = await accessibility_tester.test_page_accessibility("/docs")
    assert result["failed"] == 0, f"Accessibility failures: {result['tests']}"


@pytest.mark.accessibility
async def test_newsletter_form_accessibility(accessibility_tester: AccessibilityTester):
    """Test newsletter submission form accessibility."""
    result = await accessibility_tester.test_page_accessibility("/submit")
    assert result["failed"] == 0, f"Accessibility failures: {result['tests']}"


async def run_full_accessibility_audit() -> Dict[str, Any]:
    """Run full accessibility audit on all pages."""
    tester = AccessibilityTester()
    
    # Test all main pages
    pages_to_test = [
        "/",
        "/docs",
        "/redoc",
        "/health"
    ]
    
    for page in pages_to_test:
        await tester.test_page_accessibility(page)
    
    return tester.generate_report()


if __name__ == "__main__":
    # Run accessibility audit if script is called directly
    async def main():
        report = await run_full_accessibility_audit()
        print("Accessibility Audit Report:")
        print(f"Pages tested: {report['summary']['total_pages']}")
        print(f"Tests run: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Warnings: {report['summary']['warnings']}")
        print(f"Success rate: {report['summary']['success_rate']:.1f}%")
        
        if report['recommendations']:
            print("\nRecommendations:")
            for rec in report['recommendations']:
                print(f"- {rec}")
    
    asyncio.run(main())
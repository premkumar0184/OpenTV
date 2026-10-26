package org.opentv.launcher;

import org.junit.Test;
import static org.junit.Assert.*;

/**
 * Unit tests for VendorAdapter:
 * - Brand detection enum contract
 * - Philips HDMI device type suffix stripping
 * - Vendor package and service intent constants
 */
public class VendorAdapterTest {

    @Test
    public void testBrandEnumConstants() {
        VendorAdapter.Brand[] brands = VendorAdapter.Brand.values();
        assertEquals(4, brands.length);
        assertEquals(VendorAdapter.Brand.TCL, VendorAdapter.Brand.valueOf("TCL"));
        assertEquals(VendorAdapter.Brand.PHILIPS, VendorAdapter.Brand.valueOf("PHILIPS"));
        assertEquals(VendorAdapter.Brand.SONY, VendorAdapter.Brand.valueOf("SONY"));
        assertEquals(VendorAdapter.Brand.GENERIC, VendorAdapter.Brand.valueOf("GENERIC"));
    }

    @Test
    public void testStripDeviceTypeWithPhilipsSuffixes() {
        assertEquals("HDMI 1", VendorAdapter.stripDeviceType("HDMI 1&BLURAY"));
        assertEquals("HDMI 2", VendorAdapter.stripDeviceType("HDMI 2&COMPUTER"));
        assertEquals("HDMI 3", VendorAdapter.stripDeviceType("HDMI 3&GAME"));
        assertEquals("Port 1", VendorAdapter.stripDeviceType("Port 1&SET_TOP_BOX"));
    }

    @Test
    public void testStripDeviceTypeWithoutSuffixes() {
        assertEquals("HDMI 1", VendorAdapter.stripDeviceType("HDMI 1"));
        assertEquals("Input A", VendorAdapter.stripDeviceType("Input A"));
        assertEquals("", VendorAdapter.stripDeviceType(""));
        assertEquals("HDMI", VendorAdapter.stripDeviceType(null));
    }

    @Test
    public void testStripDeviceTypeWithAmpersandInName() {
        // Short or lowercase tokens after ampersand should not be stripped as Philips device type
        assertEquals("R&D Input", VendorAdapter.stripDeviceType("R&D Input"));
        assertEquals("A&B", VendorAdapter.stripDeviceType("A&B"));
    }

    @Test
    public void testVendorConstants() {
        assertEquals("com.tcl.settings.SHOW_WINDOW", VendorAdapter.TCL_SHOW_WINDOW);
        assertEquals("com.tcl.settings", VendorAdapter.TCL_PACKAGE);
        assertEquals("com.tcl.settings.ShowWindowService", VendorAdapter.TCL_SERVICE);

        assertEquals("com.sony.dtv.systemui.quicklauncher", VendorAdapter.SONY_QUICKLAUNCHER_PACKAGE);
        assertEquals("com.sony.dtv.systemui.quicklauncher.LaunchActivity", VendorAdapter.SONY_QUICKLAUNCHER_ACTIVITY);
    }
}

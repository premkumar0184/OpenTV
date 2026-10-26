package org.opentv.launcher;

import org.junit.Test;
import java.lang.reflect.Field;
import static org.junit.Assert.*;

/**
 * Unit tests for OledProtectionService:
 * - OLED protection timeout constants and pure black color token
 * - Pixel shift orbital coordinates bounded strictly within [-2, +2] subpixel range
 * - Service lifecycle and safe detach under headless test environments
 */
public class OledProtectionServiceTest {

    @Test
    public void testOledProtectionConstants() {
        assertEquals(180_000L, OledProtectionService.DEFAULT_INACTIVITY_TIMEOUT_MS);
        assertEquals(60_000L, OledProtectionService.PIXEL_SHIFT_INTERVAL_MS);
        assertEquals(0xFF000000, OledProtectionService.PURE_BLACK_COLOR);
    }

    @Test
    public void testShiftOrbitBounds() throws Exception {
        Field orbitField = OledProtectionService.class.getDeclaredField("SHIFT_ORBIT");
        orbitField.setAccessible(true);
        int[][] orbit = (int[][]) orbitField.get(null);

        assertNotNull("SHIFT_ORBIT must not be null", orbit);
        assertEquals("SHIFT_ORBIT should define a 10-step orbital sequence", 10, orbit.length);

        for (int i = 0; i < orbit.length; i++) {
            int[] coord = orbit[i];
            assertEquals("Each orbit point must be [dx, dy]", 2, coord.length);
            int dx = coord[0];
            int dy = coord[1];
            assertTrue("Shift dx at step " + i + " (" + dx + ") must be within [-2, +2]", dx >= -2 && dx <= 2);
            assertTrue("Shift dy at step " + i + " (" + dy + ") must be within [-2, +2]", dy >= -2 && dy <= 2);
        }
    }

    @Test
    public void testServiceLifecycle() {
        OledProtectionService service = new OledProtectionService();
        service.configure(60, true);
        service.onUserInteraction();
        service.stopInactivityTimer();
        service.detach();
    }

    @Test
    public void testStepPixelShiftResilience() {
        OledProtectionService service = new OledProtectionService();
        // Should safely no-op when views are null
        for (int i = 0; i < 25; i++) {
            service.stepPixelShift();
        }
    }

    @Test
    public void testIsOledDeviceCheck() {
        // Under standard JVM runner, default build props should not trigger false positives
        boolean isOled = OledProtectionService.isOledDevice();
        assertFalse(isOled);
    }
}

package org.opentv.launcher;

import android.net.Uri;
import org.junit.Test;
import java.util.List;
import static org.junit.Assert.*;

/**
 * Unit tests for TvInputHelper:
 * - Null and empty safety across query and dispatch methods
 * - HdmiInput data representation
 * - Default physical input limits
 */
public class TvInputHelperTest {

    @Test
    public void testMaxInputsDefault() {
        assertEquals(4, TvInputHelper.MAX_INPUTS_DEFAULT);
    }

    @Test
    public void testQueryHdmiInputsNullContext() {
        List<TvInputHelper.HdmiInput> inputs = TvInputHelper.queryHdmiInputs(null, 4);
        assertNotNull(inputs);
        assertTrue(inputs.isEmpty());
    }

    @Test
    public void testBuildLaunchIntentsNullGuards() {
        // Null context
        assertTrue(TvInputHelper.buildLaunchIntents(null, "com.google.android.tv/.HdmiInputService/HW0").isEmpty());

        // Null or blank inputId
        assertTrue(TvInputHelper.buildLaunchIntents(null, null).isEmpty());
        assertTrue(TvInputHelper.buildLaunchIntents(null, "").isEmpty());
        assertTrue(TvInputHelper.buildLaunchIntents(null, "   ").isEmpty());
    }

    @Test
    public void testLaunchInputNullContext() {
        assertFalse(TvInputHelper.launchInput(null, "HW0"));
        assertFalse(TvInputHelper.launchInput(null, null));
    }

    @Test
    public void testHdmiInputModel() {
        Uri mockUri = null;
        TvInputHelper.HdmiInput input = new TvInputHelper.HdmiInput("HW0", "PlayStation 5", mockUri, false);
        assertEquals("HW0", input.id);
        assertEquals("PlayStation 5", input.label);
        assertNull(input.passthroughUri);
        assertFalse(input.isHidden);
    }
}

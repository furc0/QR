package ru.qrcatalogue.mobile;
import org.junit.Test;
import static org.junit.Assert.*;
public class LocatorTest {
 @Test public void codes(){
  assertEquals("/n/000125",Locator.path(" 000125 "));
  assertEquals("/n/123",Locator.path("QR:123"));
  assertEquals("/s/abc",Locator.path("https://old.example/s/abc"));
  assertNull(Locator.path("0"));
  assertNull(Locator.path("https://other.example/login"));
  assertNull(Locator.path("javascript:alert(1)"));
 }
 @Test public void origins() throws Exception {
  assertEquals("http://192.168.43.5:8765",Locator.origin("192.168.43.5"));
  assertEquals("https://qr.example",Locator.origin("https://qr.example:443/"));
  try {Locator.origin("http://evil.example"); fail();} catch(IllegalArgumentException expected){}
 }
}

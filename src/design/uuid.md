# UUID

In the light-portal database, we are using UUID for most of the keys in order to support event replay between multiple environments. To balance database performance with the need for URL-friendly, we are using the PostgreSQL native UUID type for the key. 

```
CREATE TABLE your_table (
    id UUID PRIMARY KEY,
    -- other columns
);
```

The PostgreSQL can only generate UUIDv4 and it causes index locality problem. So we are using Java to generate UUIDv7 which is Time-Ordered UUID. These embed a timestamp, making them roughly sequential and significantly improving index locality and insert performance. You'll need a library for this.

```
import com.github.f4b6a3.uuid.UuidCreator;
import java.util.UUID;

// In your entity or service
UUID primaryKey = UuidCreator.getTimeOrderedEpoch(); // UUIDv7
// Store this 'primaryKey' directly.
```

In light-4j utility module, we have a UuidUtil class that can generate the UUIDv7 and also encode/decode to base64 string. 

Here is the class. 

```
package com.networknt.utility;

import com.github.f4b6a3.uuid.UuidCreator;
import java.util.Base64;
import java.util.UUID;
import java.nio.ByteBuffer;

public class UuidUtil {

    // Use Java 8's built-in Base64 encoder/decoder
    private static final Base64.Encoder URL_SAFE_ENCODER = Base64.getUrlEncoder().withoutPadding();
    private static final Base64.Decoder URL_SAFE_DECODER = Base64.getUrlDecoder();

    public static UUID getUUID() {
        return UuidCreator.getTimeOrderedEpoch(); // UUIDv7
    }

    /**
     * Generate a UUID and encode it to a URL-safe Base64 string.
     *
     * @return A URL-safe Base64 encoded UUID string.
     */
    public static String uuidToBase64(UUID uuid) {
        ByteBuffer bb = ByteBuffer.wrap(new byte[16]);
        bb.putLong(uuid.getMostSignificantBits());
        bb.putLong(uuid.getLeastSignificantBits());
        return URL_SAFE_ENCODER.encodeToString(bb.array());
    }

    /**
     * Decode a URL-safe Base64 string back to a UUID.
     *
     * @param base64 A URL-safe Base64 encoded UUID string.
     * @return The decoded UUID.
     */
    public static UUID base64ToUuid(String base64) {
        byte[] bytes = URL_SAFE_DECODER.decode(base64);
        ByteBuffer bb = ByteBuffer.wrap(bytes);
        long high = bb.getLong();
        long low = bb.getLong();
        return new UUID(high, low);
    }

}

```

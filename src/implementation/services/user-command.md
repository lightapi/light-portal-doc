# User Command Service
- [Github Link](https://github.com/lightapi/user-command)

## 1. CancelOrder Handler

### Key Steps
1. **Extracting Data**: Extracts `email`, `merchantUserId`, `orderId`, and `hostId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `OrderCancelledEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `email` (String): User email.
- `merchantUserId` (String): Merchant user identifier.
- `orderId` (String): Order identifier.
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/cancelOrder/0.1.0`

## 2. ChangePassword Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `oldPassword`, `newPassword`, and `passwordConfirm` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Password Hashing**: Hashes the new and old passwords.
4. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
5. **Event Creation**: Constructs an `EventId` and `PasswordChangedEvent` with the extracted data.
6. **Serialization**: Serializes the event using `AvroSerializer`.
7. **Kafka Producer**: Sends the serialized event to a Kafka topic.
8. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `oldPassword` (String): Old password.
- `newPassword` (String): New password.
- `passwordConfirm` (String): Password confirmation.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/changePassword/0.1.0`

## 3. ConfirmUser Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `email`, and `token` from the input map.
2. **Event Creation**: Constructs an `EventId` and `UserConfirmedEvent` with the extracted data.
3. **Serialization**: Serializes the event using `AvroSerializer`.
4. **Kafka Producer**: Sends the serialized event to a Kafka topic.
5. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `email` (String): User email.
- `token` (String): Confirmation token.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/confirmUser/0.1.0`

## 4. CreateOrder Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `merchantUserId`, and `order` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `OrderCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `merchantUserId` (String): Merchant user identifier.
- `order` (Map): Order details.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/createOrder/0.1.0`

## 5. CreateSocialUser Handler

### Key Steps
1. **Extracting Data**: Extracts `email`, `userId`, `hostId`, `firstName`, `lastName`, and `language` from the input map.
2. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
3. **Event Creation**: Constructs an `EventId` and `SocialUserCreatedEvent` with the extracted data.
4. **Serialization**: Serializes the event using `AvroSerializer`.
5. **Kafka Producer**: Sends the serialized event to a Kafka topic.
6. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `email` (String): User email.
- `userId` (String): User identifier.
- `hostId` (String): Host identifier.
- `firstName` (String): User's first name.
- `lastName` (String): User's last name.
- `language` (String): User's preferred language.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/createSocialUser/0.1.0`

## 6. CreateUser Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `email`, `entityId`, `userType`, `password`, and `passwordConfirm` from the input map.
2. **User Verification**: Ensures the email and user ID do not already exist.
3. **Password Hashing**: Hashes the password.
4. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
5. **Event Creation**: Constructs an `EventId` and `UserCreatedEvent` with the extracted data.
6. **Serialization**: Serializes the event using `AvroSerializer`.
7. **Kafka Producer**: Sends the serialized event to a Kafka topic.
8. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `email` (String): User email.
- `entityId` (String): Entity identifier.
- `userType` (String): User type.
- `password` (String): User password.
- `passwordConfirm` (String): Password confirmation.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/createUser/0.1.0`

## 7. DeletePayment Handler

### Key Steps
1. **Extracting Data**: Extracts `email` and `hostId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PaymentDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `email` (String): User email.
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/deletePayment/0.1.0`

## 8. DeleteUserById Handler

### Key Steps
1. **Extracting Data**: Extracts `userId` and `hostId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `UserDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `userId` (String): User identifier.
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/deleteUserById/0.1.0`

## 9. DeliverOrder Handler

### Key Steps
1. **Extracting Data**: Extracts `email`, `hostId`, `orderId`, and `customerUserId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `OrderDeliveredEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `email` (String): User email.
- `hostId` (String): Host identifier.
- `orderId` (String): Order identifier.
- `customerUserId` (String): Customer user identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/deliverOrder/0.1.0`

## 10. ForgetPassword Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` and `email` from the input map.
2. **User Verification**: Ensures the email exists in the system.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PasswordForgotEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Email Sending**: Sends a forget password email to the user.
8. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `email` (String): User email.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/forgetPassword/0.1.0`

## 11. LockUser Handler

### Key Steps
1. **Extracting Data**: Extracts `userId` and `hostId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `UserLockedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `userId` (String): User identifier.
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/lockUser/0.1.0`

## 12. UnlockUser Handler

### Key Steps
1. **Extracting Data**: Extracts `userId` and `hostId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `UserUnlockedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `userId` (String): User identifier.
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/unlockUser/0.1.0`

## 13. UpdatePayment Handler

### Key Steps
1. **Extracting Data**: Extracts `email`, `hostId`, and `payments` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PaymentUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `email` (String): User email.
- `hostId` (String): Host identifier.
- `payments` (Map): Payment details.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/updatePayment/0.1.0`

## 14. UpdateRoles Handler

### Key Steps
1. **Extracting Data**: Extracts `email`, `hostId`, and `roles` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `UserRolesUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `email` (String): User email.
- `hostId` (String): Host identifier.
- `roles` (String): Updated roles.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/updateRoles/0.1.0`

## 15. UpdateUserById Handler

### Key Steps
1. **Extracting Data**: Extracts `userId`, `hostId`, and `userDetails` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `UserUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `userId` (String): User identifier.
- `hostId` (String): Host identifier.
- `userDetails` (Map): User details.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/updateUserById/0.1.0`

## 16. VerifyUser Handler

### Key Steps
1. **Extracting Data**: Extracts `userId` and `hostId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `UserVerifiedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `userId` (String): User identifier.
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/verifyUser/0.1.0`

## 17. PaymentNonce Handler

### Key Steps
1. **Extracting Data**: Extracts `userId` and `hostId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PaymentNonceEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `userId` (String): User identifier.
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/paymentNonce/0.1.0`

## 18. ResetPassword Handler

### Key Steps
1. **Extracting Data**: Extracts `email`, `hostId`, `token`, `newPassword`, and `passwordConfirm` from the input map.
2. **User Verification**: Ensures the email exists in the system.
3. **Password Hashing**: Hashes the new password.
4. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
5. **Event Creation**: Constructs an `EventId` and `PasswordResetEvent` with the extracted data.
6. **Serialization**: Serializes the event using `AvroSerializer`.
7. **Kafka Producer**: Sends the serialized event to a Kafka topic.
8. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `email` (String): User email.
- `hostId` (String): Host identifier.
- `token` (String): Reset token.
- `newPassword` (String): New password.
- `passwordConfirm` (String): Password confirmation.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/resetPassword/0.1.0`

## 19. SendMessage Handler

### Key Steps
1. **Extracting Data**: Extracts `userId`, `subject`, `content`, and `hostId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PrivateMessageSentEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `userId` (String): User identifier.
- `subject` (String): Message subject.
- `content` (String): Message content.
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/user/sendMessage/0.1.0`

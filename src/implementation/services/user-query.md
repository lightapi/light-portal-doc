# User Query Service
- [Github Link](https://github.com/lightapi/user-query)

## 1. GetClientToken Handler

### Key Steps
1. **Extracting Data**: Extracts `clientId` and `clientSecret` from the input map.
2. **User Authentication**: Verifies the client credentials.
3. **Token Generation**: Generates a token for the client.
4. **Response Handling**: Returns the generated token.

### Input
- `clientId` (String): Client identifier.
- `clientSecret` (String): Client secret.

### Output
- `token` (String): Generated token for the client.

### Endpoint
- `lightapi.net/client/getClientToken/0.1.0`

## 2. GetCustomerOrder Handler

### Key Steps
1. **Extracting Data**: Extracts `customerId` and `orderId` from the input map.
2. **Order Retrieval**: Fetches the order details for the given customer and order ID.
3. **Response Handling**: Returns the order details.

### Input
- `customerId` (String): Customer identifier.
- `orderId` (String): Order identifier.

### Output
- `orderDetails` (Object): Details of the order.

### Endpoint
- `lightapi.net/customer/getCustomerOrder/0.1.0`

## 3. GetMerchantOrder Handler

### Key Steps
1. **Extracting Data**: Extracts `merchantId` and `orderId` from the input map.
2. **Order Retrieval**: Fetches the order details for the given merchant and order ID.
3. **Response Handling**: Returns the order details.

### Input
- `merchantId` (String): Merchant identifier.
- `orderId` (String): Order identifier.

### Output
- `orderDetails` (Object): Details of the order.

### Endpoint
- `lightapi.net/merchant/getMerchantOrder/0.1.0`

## 4. GetNonceByUserId Handler

### Key Steps
1. **Extracting Data**: Extracts `userId` from the input map.
2. **Nonce Retrieval**: Fetches a nonce for the given user ID.
3. **Response Handling**: Returns the nonce.

### Input
- `userId` (String): User identifier.

### Output
- `nonce` (String): Generated nonce for the user.

### Endpoint
- `lightapi.net/user/getNonceByUserId/0.1.0`

## 5. GetNotification Handler

### Key Steps
1. **Extracting Data**: Extracts `notificationId` from the input map.
2. **Notification Retrieval**: Fetches the notification details for the given notification ID.
3. **Response Handling**: Returns the notification details.

### Input
- `notificationId` (String): Notification identifier.

### Output
- `notificationDetails` (Object): Details of the notification.

### Endpoint
- `lightapi.net/notification/getNotification/0.1.0`

## 6. GetPayment Handler

### Key Steps
1. **Extracting Data**: Extracts `paymentId` from the input map.
2. **Payment Retrieval**: Fetches the payment details for the given payment ID.
3. **Response Handling**: Returns the payment details.

### Input
- `paymentId` (String): Payment identifier.

### Output
- `paymentDetails` (Object): Details of the payment.

### Endpoint
- `lightapi.net/payment/getPayment/0.1.0`

## 7. GetPaymentById Handler

### Key Steps
1. **Extracting Data**: Extracts `paymentId` from the input map.
2. **Payment Retrieval**: Fetches the payment details for the given payment ID.
3. **Response Handling**: Returns the payment details.

### Input
- `paymentId` (String): Payment identifier.

### Output
- `paymentDetails` (Object): Details of the payment.

### Endpoint
- `lightapi.net/payment/getPaymentById/0.1.0`

## 8. GetPrivateMessage Handler

### Key Steps
1. **Extracting Data**: Extracts `messageId` from the input map.
2. **Message Retrieval**: Fetches the private message details for the given message ID.
3. **Response Handling**: Returns the message details.

### Input
- `messageId` (String): Message identifier.

### Output
- `messageDetails` (Object): Details of the private message.

### Endpoint
- `lightapi.net/message/getPrivateMessage/0.1.0`

## 9. GetReference Handler

### Key Steps
1. **Extracting Data**: Extracts `referenceId` from the input map.
2. **Reference Retrieval**: Fetches the reference details for the given reference ID.
3. **Response Handling**: Returns the reference details.

### Input
- `referenceId` (String): Reference identifier.

### Output
- `referenceDetails` (Object): Details of the reference.

### Endpoint
- `lightapi.net/reference/getReference/0.1.0`

## 10. GetRolesByEmail Handler

### Key Steps
1. **Extracting Data**: Extracts `email` from the input map.
2. **Roles Retrieval**: Fetches the roles associated with the given email.
3. **Response Handling**: Returns the roles.

### Input
- `email` (String): Email address.

### Output
- `roles` (List): List of roles associated with the email.

### Endpoint
- `lightapi.net/user/getRolesByEmail/0.1.0`

## 11. GetUserLabel Handler

### Key Steps
1. **Extracting Data**: Extracts `userId` from the input map.
2. **Label Retrieval**: Fetches the label associated with the given user ID.
3. **Response Handling**: Returns the label.

### Input
- `userId` (String): User identifier.

### Output
- `label` (String): Label associated with the user.

### Endpoint
- `lightapi.net/user/getUserLabel/0.1.0`

## 12. ListUserByHostId Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **User List Retrieval**: Fetches the list of users associated with the given host ID.
3. **Response Handling**: Returns the list of users.

### Input
- `hostId` (String): Host identifier.

### Output
- `userList` (List): List of users associated with the host ID.

### Endpoint
- `lightapi.net/user/listUserByHostId/0.1.0`

## 13. LoginUser Handler

### Key Steps
1. **Extracting Data**: Extracts `username` and `password` from the input map.
2. **User Authentication**: Verifies the user credentials.
3. **Token Generation**: Generates a token for the user.
4. **Response Handling**: Returns the generated token.

### Input
- `username` (String): Username.
- `password` (String): Password.

### Output
- `token` (String): Generated token for the user.

### Endpoint
- `lightapi.net/user/loginUser/0.1.0`

## 14. QueryUserByEmail Handler

### Key Steps
1. **Extracting Data**: Extracts `email` from the input map.
2. **User Retrieval**: Fetches the user details associated with the given email.
3. **Response Handling**: Returns the user details.

### Input
- `email` (String): Email address.

### Output
- `userDetails` (Object): Details of the user.

### Endpoint
- `lightapi.net/user/queryUserByEmail/0.1.0`

## 15. QueryUserById Handler

### Key Steps
1. **Extracting Data**: Extracts `userId` from the input map.
2. **User Retrieval**: Fetches the user details associated with the given user ID.
3. **Response Handling**: Returns the user details.

### Input
- `userId` (String): User identifier.

### Output
- `userDetails` (Object): Details of the user.

### Endpoint
- `lightapi.net/user/queryUserById/0.1.0`

## 16. QueryUserByTypeEntityId Handler

### Key Steps
1. **Extracting Data**: Extracts `type` and `entityId` from the input map.
2. **User Retrieval**: Fetches the user details associated with the given type and entity ID.
3. **Response Handling**: Returns the user details.

### Input
- `type` (String): Type of the entity.
- `entityId` (String): Entity identifier.

### Output
- `userDetails` (Object): Details of the user.

### Endpoint
- `lightapi.net/user/queryUserByTypeEntityId/0.1.0`

## 17. QueryUserByWallet Handler

### Key Steps
1. **Extracting Data**: Extracts `walletId` from the input map.
2. **User Retrieval**: Fetches the user details associated with the given wallet ID.
3. **Response Handling**: Returns the user details.

### Input
- `walletId` (String): Wallet identifier.

### Output
- `userDetails` (Object): Details of the user.

### Endpoint
- `lightapi.net/user/queryUserByWallet/0.1.0`

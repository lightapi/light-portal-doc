# Sign In

## Portal Dashboard

The **Portal Dashboard** is served by the `portal-view` single-page application. 

- **Guest User Access**:  
  Upon landing on the dashboard, a guest user can:
  - View certain menus.
  - Perform limited actions within the application.

- **Accessing Privileged Features**:  
  To access additional features:
  1. Click the **User** button.
  2. Select the **Sign In** menu item.

## Login View

- **Redirection to Login View**:  
  When the **Sign In** menu item is clicked, the browser is redirected to the **Login View** single-page application. This application is served by the same instance of `light-gateway` and handles user authentication against the OAuth 2.0 server (**OAuth Kafka**) to initiate the Authorization Code grant flow.

- **OAuth 2.0 Client ID**:  
  The `client_id` is included in the redirect URL as a query parameter. This ensures that the `client_id` is sent to the OAuth 2.0 server to obtain the authorization code. In this context, the `client_id` is associated with the `portal-view` application.

- **Login View Responsibilities**:  
  The **Login View** is a shared single-page application used by all other SPAs across various hosts. It is responsible for:
  - Authenticating users.
  - Ensuring that user credentials are not passed to any other single-page applications or business APIs.

- **SaaS Deployment in the Cloud**:  
  In a SaaS environment, all users are authenticated by the OAuth 2.0 server using the `light-portal` user database. As a result, the user type does not need to be passed from the **Login View**.

- **On-Premise Deployment**:  
  For on-premise deployments, a customized **Login View** should include a radio button for selecting the user type. Typical options for most organizations are:
  - **Employee (E)**
  - **Customer (C)**

- **Customized Authentication**:  
  Based on the selected user type:
  - Employees are authenticated via **Active Directory**.
  - Customers are authenticated using the **customer database**.

  A customized authenticator implementation should handle this logic, ensuring the correct authentication method is invoked for each user type.

## Login Form Submission

- **Form Submission Endpoint**:  
  `/oauth2/N2CMw0HGQXeLvC1wBfln2A/code`

- **Request Details**:  
  - **Headers**:  
    - `Content-Type`: `application/x-www-form-urlencoded`
  - **Method**:  
    - `POST`
  - **Body Parameters**:  
    - `j_username`: The user's username.  
    - `j_password`: The user's password.  
    - `remember`: Indicates whether the session should persist.  
    - `client_id`: The OAuth 2.0 client identifier.  
    - `state`: A hardcoded value (requires additional work for dynamic handling).  
    - `user_type`: (Optional) Specifies the type of user (e.g., employee or customer).  
    - `redirect_uri`: (Optional) The URI to redirect after authentication.

## Light Gateway

The light-gateway instance acts as a BFF and it has a routing rule to route any request with prefix /oauth2 to kafka-oauth server. 

## OAuth Kafka

- **LightPortalAuthenticator**
  
  A request to hybrid-query:
  ``` 
  {"host":"lightapi.net","service":"user","action":"loginUser","version":"0.1.0","data":{"email":"%s","password":"%s"}}
  ```
## User Query

- **LoginUser**

This handler calls loginUserByEmail method from PortalDbProviderImpl. 

## PortalDbProviderImpl

The input for this method is the user's email. Upon successful execution, the method returns a JSON string containing all user properties retrieved from the login query.

## LightPortalAuthenticator

The authenticator will utilize the user data returned from the above query to validate the password. Upon successful password verification, it will return an `Account` object with the following attributes:

- **Principal**: The user's identifier, which is the email.
- **Roles**: A collection containing a single element—the user's JSON

After the `Account` object is created and returned, control is passed to the `HostIdCodePostHandler`.

## HostIdCodePostHandler

It get the client_id from the submitted form and call dbProvider.queryClientByClientId to get client information. Upon successful, it get the Account object created by the authenticator above from the security context. 

Create a UUID authorization code and a map associates with the code. The map contains properties that need to create authorization code token. Some properties from the client and the entire user json. 

Call the ClientUtil.createAuthCode with the codeMap to create the authorization code and then redirect the code to back to the redirect uri. 

## ClientUtil.createAuthCode

The ClientUtil gets a client credentials token and call the CreateAuthCode handler in the hybrid-command to publish the code to the Kafka cluster in order to notify other party about this code. The codeMap is passed to the handler as data. 

## CreateAuthCode Handler

The handler create a MarketCodeCreatedEvent and pass the entire input map to the event as value field. 

## MarketQueryStreams

It processes the MarketCodeCreatedEvent and calls dbProvider.createMarketCode with the event.

## createMarketCode

This method in dbProvider will put the event value into cacheManager cache named "auth_code". Now, the code is ready to be query from the market-query. 

## Portal View

The HostIdCodePostHandler redirects the code to the Portal View with /authorization?code=??? and this request will be sent to the light-gateway StatelessAuthHandler.

## StatelessAuthHandler

If the request path matches to the configured authPath, it will retrieve the code from the query parameter. Then create a csrf UUID token and an AuthorizationCodeRequest to get a token via OauthHelper. This request will have the auth code, the csrf token and other properties from the configuration. The request is sent to the HostIdTokenPostHandler to create the authorization code token. 

## HostIdTokenPostHandler

It calls dbProvider.queryClientByClientId and then verify the clientId and clientSecret matches. 

It invokes ClientUtil.getAuthCodeDetail from the market-query service and calls the ClientUtil.deleteAuthCode to remove the auth code as it is one-time code.



## 







## 







  

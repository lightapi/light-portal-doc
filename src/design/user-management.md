# User Management

## User Type

In the user registration, there is option to set user type for some hosts so that different OAuth 2.0 authenticator implementations can be invoked to authenticate the user based on the type. 

User Type is an optional field and it should only be used for on-prem deployment. The dropdown list is populated from the refernece table set up for the organization. There are two different models we are support at the moment. 

1. employee and customer

This is for some origanizations that employees are authenticated with active directory and customers are authenticated from customer database or subsystem. The values in database should be E, C.

2. employee, personal and business

This is the model for banks that personal banking and business banking are separated. The values in database should be E, P, B.

This is a nullable field in database user_t table and it is not shown in the user registration form by default. 




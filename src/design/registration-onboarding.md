# User Registration and Onboarding
 
In light-portal, user management is the foundation of the authentication and authorization to access different services. 

There are two different apporaches to create an user entry in the system: Internet and Corporation. 

### Internet User

This is for Internet users to register and verify via email to a cloud Light Portal instance.

The entry point is the createUser command handle in the user-command service.


### Corporation User

This is for corporation users to onboard to a dedicated Intranet Light Portal instance.

The entry point is the onboardUser command handler in the user-comand service.


### User Password

In the user_t table, the password is nullable and onboardUser doesn't have password passed in as the authentication is done through Azure AD and ECIF etc. 

 
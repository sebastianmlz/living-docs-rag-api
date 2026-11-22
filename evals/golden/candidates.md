# Golden set: candidatos para revisar

- Modelo: `gemini-3.5-flash-lite` · llamadas: 3 · descartes: quote_length: 1, quote_not_in_source: 1
- 60 preguntas: multi 10, single 40, unanswerable 10 · en 32, es 28

Al revisar: ¿la pregunta suena real?, ¿el fragmento de verdad la responde?, ¿las no respondibles de verdad NO están en la documentación?

---

### q001 · single · es

**¿Cómo puedo incluir la definición de un cuerpo de petición en el esquema OpenAPI si decido procesar los datos crudos manualmente sin usar modelos de Pydantic?**

[advanced/path-operation-advanced-configuration.md › Path Operation Advanced Configuration > OpenAPI Extra > Custom OpenAPI *path operation* schema](https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/)

> So, you could add additional data to the automatically generated schema.

*Respuesta esperada:* Puedes utilizar el parámetro `openapi_extra` en el decorador de la ruta para fusionar un diccionario personalizado con el esquema OpenAPI generado automáticamente. De esta manera, es posible documentar la estructura esperada de la petición incluso si procesas los datos directamente como bytes.

---

### q002 · single · en

**Which specific libraries were chosen as the core dependencies for building FastAPI?**

[history-design-future.md › History, Design and Future > Requirements](https://fastapi.tiangolo.com/history-design-future/)

> After testing several alternatives, I decided that I was going to use Pydantic for its advantages.

[history-design-future.md › History, Design and Future > Requirements](https://fastapi.tiangolo.com/history-design-future/)

> During the development, I also contributed to Starlette, the other key requirement.

*Respuesta esperada:* FastAPI is built using Pydantic for data validation and Starlette for the web handling capabilities as its two core requirements.

---

### q003 · single · es

**¿Qué paquete externo debo instalar y utilizar actualmente para integrar una aplicación basada en WSGI en mi proyecto de FastAPI?**

[advanced/wsgi.md › Including WSGI - Flask, Django, others > Using `WSGIMiddleware`](https://fastapi.tiangolo.com/advanced/wsgi/)

> It's advised to use the `a2wsgi` package instead. The usage remains the same.

*Respuesta esperada:* Debes instalar y utilizar el paquete a2wsgi en tu proyecto. A partir de ahí, puedes importar WSGIMiddleware desde a2wsgi para envolver tu aplicación WSGI y montarla en FastAPI.

---

### q004 · single · en

**How can I dynamically change the HTTP status code of an endpoint inside my function instead of defining it statically in the decorator?**

[advanced/response-change-status-code.md › Response - Change Status Code > Use a `Response` parameter](https://fastapi.tiangolo.com/advanced/response-change-status-code/)

> You can declare a parameter of type `Response` in your *path operation function* (as you can do for cookies and headers).

*Respuesta esperada:* You can declare a parameter of type Response in your path operation function and then modify its status_code attribute directly. FastAPI will use this temporary response object to extract the updated status code for the final response.

---

### q005 · single · es

**¿Cómo puedo hacer para devolver un código de estado HTTP diferente al principal, como un 201 al crear un recurso nuevo?**

[advanced/additional-status-codes.md › Additional Status Codes > Additional status codes](https://fastapi.tiangolo.com/advanced/additional-status-codes/)

> If you want to return additional status codes apart from the main one, you can do that by returning a `Response` directly, like a `JSONResponse`, and set the additional status code directly.

*Respuesta esperada:* Para devolver códigos de estado adicionales además del principal, puedes retornar directamente una respuesta como `JSONResponse` configurando el código de estado deseado en ella.

---

### q006 · single · en

**What kind of editor support can I expect when working with the generated TypeScript client?**

[advanced/generate-clients.md › Generating SDKs > Create a TypeScript SDK > Using the SDK](https://fastapi.tiangolo.com/advanced/generate-clients/)

> Notice the autocompletion for `name` and `price`, that was defined in the FastAPI application, in the `Item` model.

*Respuesta esperada:* When using the generated TypeScript client, you get autocompletion for available methods, request payloads, and response objects, along with inline error checking for the data you send.

---

### q007 · single · es

**¿Cómo puedo hacer para obtener únicamente la ruta URL sin incluir el dominio ni los parámetros de consulta en una plantilla?**

[advanced/templates.md › Templates > Writing templates > URL paths in templates](https://fastapi.tiangolo.com/advanced/templates/)

> For links to the same site, you can use the .path attribute to get only the URL path

*Respuesta esperada:* Puedes utilizar el atributo .path en los enlaces dentro de tus plantillas para obtener únicamente la ruta de la URL. Esto excluye el esquema, el host, los parámetros de consulta y el fragmento.

---

### q008 · single · en

**Does FastAPI restrict whether I can mix asynchronous and synchronous functions when writing dependencies and path operations?**

[tutorial/dependencies/index.md › Dependencies > To `async` or not to `async`](https://fastapi.tiangolo.com/tutorial/dependencies/)

> You can use async def or normal def. And you can declare dependencies with async def inside of normal def path operation functions, or def dependencies inside of async def path operation functions, etc.

*Respuesta esperada:* No, FastAPI does not restrict this. You can freely mix 'async def' and normal 'def' functions for both dependencies and path operations in any combination you need.

---

### q009 · single · es

**¿Cómo puedo leer el cuerpo de una petición dentro de un manejador de excepciones cuando ocurre un error de validación?**

[how-to/custom-request-and-route.md › Custom Request and APIRoute class > Accessing the request body in an exception handler](https://fastapi.tiangolo.com/how-to/custom-request-and-route/)

> If an exception occurs, the `Request` instance will still be in scope, so we can read and make use of the request body when handling the error

*Respuesta esperada:* Puedes envolver la lógica de la ruta en un bloque try/except para capturar la excepción de validación. Como la instancia de la petición sigue disponible en el ámbito, puedes leer el cuerpo usando await request.body() para incluirlo en los detalles del error.

---

### q010 · single · en

**How can I configure a Pydantic model for headers so that it becomes completely optional?**

[tutorial/header-param-models.md › Header Parameter Models > Optional Header Parameter Models](https://fastapi.tiangolo.com/tutorial/header-param-models/)

> Declare a header parameter model with `| None` and a default of `None` to make the group optional.

*Respuesta esperada:* You can make a header parameter model optional by defining it with `| None` and setting its default value to `None`. If the headers are not provided, the model instance will evaluate to `None`.

---

### q011 · single · es

**¿Cómo puedo medir el tiempo exacto que tarda mi aplicación en procesar una petición para incluirlo en una cabecera personalizada?**

[tutorial/middleware.md › Middleware > Create a middleware > Before and after the `response`](https://fastapi.tiangolo.com/tutorial/middleware/)

> Here we use time.perf_counter() instead of time.time() because it can be more precise for these use cases.

*Respuesta esperada:* Puedes utilizar la función time.perf_counter() en lugar de time.time() dentro de tu middleware para obtener una mayor precisión al medir el tiempo que toma procesar la solicitud y generar la respuesta.

---

### q012 · single · en

**How can I convert a Pydantic model and a datetime object into a format that a standard JSON database can accept?**

[tutorial/encoder.md › JSON Compatible Encoder > Using the `jsonable_encoder`](https://fastapi.tiangolo.com/tutorial/encoder/)

> You can use jsonable_encoder for that.

*Respuesta esperada:* You can use the jsonable_encoder function to convert non-JSON compatible objects like Pydantic models and datetime objects into standard Python data structures like dictionaries and strings that are fully compatible with JSON.

---

### q013 · single · es

**¿De qué forma está estructurado el campo de ejemplos específico de OpenAPI dentro de la documentación?**

[tutorial/schema-extra-example.md › Declare Request Example Data > `examples` in JSON Schema - OpenAPI > OpenAPI-specific `examples`](https://fastapi.tiangolo.com/tutorial/schema-extra-example/)

> The shape of this OpenAPI-specific field examples is a dict with multiple examples (instead of a list), each with extra information that will be added to OpenAPI too.

*Respuesta esperada:* El campo de ejemplos específico de OpenAPI tiene la forma de un diccionario con múltiples ejemplos en lugar de una lista, y cada uno incluye información adicional que se añade directamente a OpenAPI.

---

### q014 · single · en

**How can I change the default path for the Swagger documentation interface and completely turn off the alternative ReDoc interface?**

[tutorial/metadata.md › Metadata and Docs URLs > Docs URLs](https://fastapi.tiangolo.com/tutorial/metadata/)

> You can set its URL with the parameter docs_url.

*Respuesta esperada:* You can change the Swagger UI path by passing a custom route to the docs_url parameter when initializing FastAPI, and you can disable ReDoc by setting redoc_url to None.

---

### q015 · single · es

**¿Cómo debo declarar una función en FastAPI si necesito usar la instrucción await en su interior?**

[async.md › Concurrency and async / await > `async` and `await`](https://fastapi.tiangolo.com/async/)

> For `await` to work, it has to be inside a function that supports this asynchronicity. To do that, you just declare it with `async def`

*Respuesta esperada:* Para que la instrucción await funcione, debes declarar la función utilizando async def en lugar de una definición convencional con def.

---

### q016 · single · en

**Which FastAPI release completely removed the compatibility layer for older Pydantic versions?**

[how-to/migrate-from-pydantic-v1-to-pydantic-v2.md › Migrate from Pydantic v1 to Pydantic v2](https://fastapi.tiangolo.com/how-to/migrate-from-pydantic-v1-to-pydantic-v2/)

> FastAPI 0.128.0 dropped support for `pydantic.v1` as well, so the latest versions of FastAPI require Pydantic v2.

*Respuesta esperada:* FastAPI version 0.128.0 removed support for pydantic.v1 entirely. As a result, recent versions of FastAPI exclusively require Pydantic v2.

---

### q017 · single · es

**¿Cómo puedo servir aplicaciones frontend estáticas generadas por herramientas como React o Vite dentro de mi proyecto?**

[tutorial/frontend.md › Frontend](https://fastapi.tiangolo.com/tutorial/frontend/)

> You can serve static frontend apps with app.frontend() (or router.frontend()).

*Respuesta esperada:* Puedes servir aplicaciones frontend estáticas utilizando los métodos app.frontend() o router.frontend(). Esto permite servir directorios con archivos compilados sin afectar las rutas normales de la API, ya que FastAPI verifica primero las operaciones de ruta.

---

### q018 · single · en

**How can I avoid slowing down automated tests when my application needs to load a heavy machine learning model from disk?**

[advanced/events.md › Lifespan Events > Use Case](https://fastapi.tiangolo.com/advanced/events/)

> That's what we'll solve, let's load the model before the requests are handled, but only right before the application starts receiving requests

*Respuesta esperada:* Load the model with a lifespan function, right before the application starts receiving requests instead of at module import time, so simple automated tests don't have to wait for it to load.

---

### q019 · single · es

**¿Ocultar las interfaces de documentación en producción realmente protege mi API?**

[how-to/conditional-openapi.md › Conditional OpenAPI > About security, APIs, and docs](https://fastapi.tiangolo.com/how-to/conditional-openapi/)

> Hiding your documentation user interfaces in production *shouldn't* be the way to protect your API.

*Respuesta esperada:* No, ocultar la documentación no añade seguridad real ni evita que las operaciones sigan disponibles. Para proteger una API se deben implementar mejores prácticas como usar modelos Pydantic bien definidos, configurar permisos con dependencias y utilizar herramientas criptográficas.

---

### q020 · single · en

**How can I launch multiple worker processes for my FastAPI app using the command line?**

[deployment/server-workers.md › Server Workers - Uvicorn with Workers > Multiple Workers](https://fastapi.tiangolo.com/deployment/server-workers/)

> You can start multiple workers with the `--workers` command line option:

*Respuesta esperada:* You can start multiple worker processes by using the --workers command line option when running your application.

---

### q021 · single · es

**¿Para qué se utiliza la librería Pydantic en Python?**

[python-types.md › Python Types Intro > Pydantic models](https://fastapi.tiangolo.com/python-types/)

> Pydantic is a Python library to perform data validation.

*Respuesta esperada:* Pydantic es una librería de Python que se utiliza para realizar la validación de datos. Permite definir la estructura de los datos mediante clases con atributos tipados para validar y convertir los valores.

---

### q022 · single · en

**What features and components are already pre-configured in the official FastAPI full stack template?**

[project-generation.md › Full Stack FastAPI Template](https://fastapi.tiangolo.com/project-generation/)

> it includes a lot of the initial setup, security, database and some API endpoints already done for you.

*Respuesta esperada:* The official full stack template includes pre-configured features such as initial project setup, security configurations, database setup, and a few ready-to-use API endpoints to help you start your project quickly.

---

### q023 · single · es

**¿Cómo maneja FastAPI la estructura de los permisos cuando se usa OAuth2PasswordRequestForm?**

[tutorial/security/simple-oauth2.md › Simple OAuth2 with Password and Bearer > Code to get the `username` and `password` > Use the form data](https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/)

> The instance of the dependency class `OAuth2PasswordRequestForm` won't have an attribute `scope` with the long string separated by spaces, instead, it will have a `scopes` attribute with the actual list of strings for each scope sent.

*Respuesta esperada:* La instancia de la clase de dependencia OAuth2PasswordRequestForm no contiene un atributo scope con una cadena larga de texto separada por espacios, sino que incluye un atributo llamado scopes que almacena una lista real con cada uno de los permisos enviados.

---

### q024 · single · en

**How can I configure my FastAPI application to reject requests that include unauthorized or extra cookies?**

[tutorial/cookie-param-models.md › Cookie Parameter Models > Forbid Extra Cookies](https://fastapi.tiangolo.com/tutorial/cookie-param-models/)

> You can use Pydantic's model configuration to forbid any extra fields

*Respuesta esperada:* You can restrict unwanted cookies by setting Pydantic's model configuration to forbid extra fields. If a client sends any cookies not defined in the model, FastAPI will automatically reject the request and return an error response.

---

### q025 · single · es

**¿Hay alguna forma de evitar escribir dos veces el nombre de la clase al declarar una dependencia basada en clases en FastAPI?**

[tutorial/dependencies/classes-as-dependencies.md › Classes as Dependencies > Shortcut](https://fastapi.tiangolo.com/tutorial/dependencies/classes-as-dependencies/)

> FastAPI provides a shortcut for these cases, in where the dependency is *specifically* a class that **FastAPI** will "call" to create an instance of the class itself.

*Respuesta esperada:* Sí, FastAPI ofrece un atajo permitiendo usar simplemente `Depends()` sin pasarle parámetros cuando la dependencia es directamente una clase. De esta manera, el framework sabe que debe instanciar esa clase basándose en el tipo del parámetro.

---

### q026 · single · en

**How can I run validation dependencies on an endpoint without passing their returned values into the handler function?**

[tutorial/dependencies/dependencies-in-path-operation-decorators.md › Dependencies in path operation decorators > Add `dependencies` to the *path operation decorator*](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/)

> These dependencies will be executed/solved the same way as normal dependencies. But their value (if they return any) won't be passed to your *path operation function*.

*Respuesta esperada:* You can pass an optional list of Depends() to the dependencies argument in the path operation decorator. This ensures the dependencies are executed without passing any returned values to your path operation function.

---

### q027 · single · es

**¿Debo preocuparme por si la inclusión de múltiples routers en la aplicación principal degrada el rendimiento de las peticiones?**

[tutorial/bigger-applications.md › Bigger Applications - Multiple Files > The main `FastAPI` > Include the `APIRouter`s for `users` and `items`](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

> You don't have to worry about performance when including routers.

*Respuesta esperada:* No hay que preocuparse por el rendimiento. El sistema está diseñado para ser ligero y evitar añadir sobrecarga en las peticiones.

---

### q028 · single · en

**How can I specify an HTTP status code for my API endpoints when I don't remember the exact integer values?**

[tutorial/path-operation-configuration.md › Path Operation Configuration > Response Status Code](https://fastapi.tiangolo.com/tutorial/path-operation-configuration/)

> But if you don't remember what each number code is for, you can use the shortcut constants in status

*Respuesta esperada:* You can use the shortcut constants available in the status module provided by FastAPI instead of remembering or passing raw integer codes directly.

---

### q029 · single · es

**¿Qué ocurre si intento consultar la ruta de mis items sin haber marcado el permiso correspondiente al autenticarme en la documentación?**

[advanced/security/oauth2-scopes.md › OAuth2 scopes > Check it](https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/)

> If you don't select any scope, you will be "authenticated", but when you try to access `/users/me/` or `/users/me/items/` you will get an error saying that you don't have enough permissions.

*Respuesta esperada:* Recibirás un error indicando que no tienes los permisos suficientes para acceder a esa ruta específica, aunque la autenticación general haya sido exitosa.

---

### q030 · single · en

**Who is responsible for creating FastAPI Cloud?**

[deployment/fastapicloud.md › FastAPI Cloud > About FastAPI Cloud](https://fastapi.tiangolo.com/deployment/fastapicloud/)

> FastAPI Cloud is built by the same author and team behind FastAPI.

*Respuesta esperada:* FastAPI Cloud was created by the exact same author and team that developed FastAPI.

---

### q031 · single · es

**¿Cómo puedo validar un número decimal para asegurarme de que sea estrictamente mayor que cero pero menor que un número determinado?**

[tutorial/path-params-numeric-validations.md › Path Parameters and Numeric Validations > Number validations: floats, greater than and less than](https://fastapi.tiangolo.com/tutorial/path-params-numeric-validations/)

> As with it you can require, for example, that a value must be greater than `0`, even if it is less than `1`.

*Respuesta esperada:* Para validar números decimales puedes utilizar los parámetros gt (mayor que) y lt (menor que). De esta forma es posible exigir que un valor sea estrictamente mayor a cero aunque sea menor a uno, aceptando valores decimales intermedios pero rechazando el cero.

---

### q032 · single · en

**How does the browser confirm that an incoming response actually originates from the legitimate server?**

[deployment/https.md › About HTTPS > HTTPS for Developers > HTTPS Response](https://fastapi.tiangolo.com/deployment/https/)

> The client (browser) will know that the response comes from the correct server because it is using the cryptography they agreed using the **HTTPS certificate** before.

*Respuesta esperada:* The browser recognizes that the response originates from the correct server by relying on the cryptography they previously established through the HTTPS certificate.

---

### q033 · single · es

**¿Qué tipo de solicitud HTTP envía el navegador automáticamente al servidor antes de permitir que un frontend en un puerto diferente se comunique con él?**

[tutorial/cors.md › CORS (Cross-Origin Resource Sharing) > Steps](https://fastapi.tiangolo.com/tutorial/cors/)

> Then, the browser will send an HTTP `OPTIONS` request to the `:80`-backend

*Respuesta esperada:* El navegador envía una solicitud HTTP de tipo OPTIONS al servidor backend para verificar si este último autoriza la comunicación desde un origen diferente mediante los encabezados adecuados.

---

### q034 · single · en

**How does Pydantic handle environment variable names when loading them into the settings class attributes?**

[advanced/settings.md › Settings and Environment Variables > Pydantic `Settings` > Create the `Settings` object](https://fastapi.tiangolo.com/advanced/settings/)

> Pydantic will read the environment variables in a case-insensitive way, so, an upper-case variable APP_NAME will still be read for the attribute app_name.

*Respuesta esperada:* Pydantic reads environment variables in a case-insensitive manner. This means that an upper-case environment variable like APP_NAME will automatically match and be assigned to a lower-case attribute like app_name.

---

### q035 · single · es

**¿Es posible enviar configuraciones que requieren objetos de JavaScript directamente desde el código en Python?**

[how-to/configure-swagger-ui.md › Configure Swagger UI > JavaScript-only settings](https://fastapi.tiangolo.com/how-to/configure-swagger-ui/)

> These are **JavaScript** objects, not strings, so you can't pass them from Python code directly.

*Respuesta esperada:* No, no es posible pasarlos directamente desde el código de Python porque son objetos de JavaScript y no cadenas de texto. Para usarlos, debes sobrescribir la ruta de Swagger UI y escribir manualmente el código JavaScript necesario.

---

### q036 · single · en

**Is it a good idea to use base64 encoding for large binary files instead of standard file uploads?**

[advanced/json-base64-bytes.md › JSON with Bytes as Base64 > Base64 vs Files](https://fastapi.tiangolo.com/advanced/json-base64-bytes/)

> Base64 can encode binary data in strings, but to do it, it needs to use more characters than the original binary data, so it would normally be less efficient than regular files.

*Respuesta esperada:* No, sending binary data using base64 inside JSON is generally less efficient than using standard file uploads because it requires more characters than the original binary data. You should prefer uploading binary data as files and only use base64 if it is strictly necessary to include it in a JSON payload.

---

### q037 · single · es

**¿Cómo puedo comprobar que los archivos estáticos de la documentación están funcionando correctamente?**

[how-to/custom-docs-ui-assets.md › Custom Docs UI Static Assets (Self-Hosting) > Self-hosting JavaScript and CSS for docs > Test the static files](https://fastapi.tiangolo.com/how-to/custom-docs-ui-assets/)

> That confirms that you are being able to serve static files from your app, and that you placed the static files for the docs in the correct place.

*Respuesta esperada:* Puedes iniciar tu aplicación y visitar la URL correspondiente al archivo estático en tu navegador. Si visualizas el contenido del código, significa que los archivos se están sirviendo de forma correcta.

---

### q038 · single · en

**How can I send an email notification to a user after they perform an action without making them wait for the server to connect to the email provider?**

[tutorial/background-tasks.md › Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)

> You can define background tasks to be run *after* returning a response.

*Respuesta esperada:* You can use background tasks to run operations like sending emails after the response has already been sent to the client. This prevents the user from having to wait for slow network operations to finish.

---

### q039 · single · es

**¿Cuáles son los esquemas de seguridad que define la especificación OpenAPI?**

[tutorial/security/index.md › Security > OpenAPI](https://fastapi.tiangolo.com/tutorial/security/)

> OpenAPI defines the following security schemes:

*Respuesta esperada:* OpenAPI define cuatro esquemas principales de seguridad: apiKey, http, oauth2 y openIdConnect.

---

### q040 · single · en

**How can I make sure FastAPI documents my custom HTML response correctly in the interactive documentation?**

[advanced/custom-response.md › Custom Response - HTML, Stream, File, others > HTML Response > Document in OpenAPI and override `Response` > Return an `HTMLResponse` directly](https://fastapi.tiangolo.com/advanced/custom-response/)

> But as you passed the HTMLResponse in the response_class too, FastAPI will know how to document it in OpenAPI and the interactive docs as HTML with text/html

*Respuesta esperada:* You can ensure FastAPI documents it correctly by passing the HTMLResponse directly in the response_class parameter of your path operation decorator.

---

### q052 · unanswerable · es

**¿Cuál es el procedimiento exacto para desplegar una aplicación de FastAPI en AWS Lambda usando Serverless Framework?**

---

### q053 · unanswerable · es

**¿Cómo puedo integrar autenticación con Firebase Auth en lugar de usar OAuth2 nativo en FastAPI?**

---

### q055 · unanswerable · es

**¿Qué pasos debo seguir para conectar FastAPI con un clúster de Apache Kafka y consumir mensajes en tiempo real?**

---

### q057 · unanswerable · en

**What is the best way to connect FastAPI with a Redis cluster for caching session data?**

---

### q058 · unanswerable · en

**How do I configure Prometheus metrics export directly inside my FastAPI application?**

---

### q060 · multi · en

**How can I define a model that includes both a validated web address field and a collection for unique keywords that avoids duplicates?**

[tutorial/body-nested-models.md › Body - Nested Models > Special types and validation](https://fastapi.tiangolo.com/tutorial/body-nested-models/)

> For example, as in the `Image` model we have a `url` field, we can declare it to be an instance of Pydantic's `HttpUrl` instead of a `str`:

[tutorial/body-nested-models.md › Body - Nested Models > Set types](https://fastapi.tiangolo.com/tutorial/body-nested-models/)

> And Python has a special data type for sets of unique items, the `set`.

*Respuesta esperada:* You can use Pydantic's HttpUrl type for the URL field to ensure it is validated properly, and define the keyword collection using Python's set data type to automatically handle unique items without duplicates.

---

### q061 · multi · es

**¿Cómo se estructuran los datos al enviar múltiples objetos en formato JSON Lines y de qué manera se implementa el flujo usando yield en una ruta de FastAPI?**

[tutorial/stream-json-lines.md › Stream JSON Lines > JSON Lines](https://fastapi.tiangolo.com/tutorial/stream-json-lines/)

> In these cases, it's common to send "JSON Lines", which is a format where you send one JSON object per line.

[tutorial/stream-json-lines.md › Stream JSON Lines > Stream JSON Lines with FastAPI](https://fastapi.tiangolo.com/tutorial/stream-json-lines/)

> To stream JSON Lines with FastAPI you can, instead of using `return` in your *path operation function*, use `yield` to produce each item in turn.

*Respuesta esperada:* El formato JSON Lines consiste en enviar un objeto JSON por cada línea, separados por un carácter de nueva línea. En FastAPI se puede implementar este flujo utilizando 'yield' en lugar de 'return' dentro de la función de la ruta.

---

### q062 · multi · en

**What steps should I take before updating my application to a newer minor version of FastAPI, considering how breaking changes are handled?**

[deployment/versions.md › About FastAPI versions > Upgrading the FastAPI versions](https://fastapi.tiangolo.com/deployment/versions/)

> After you have tests, then you can upgrade the **FastAPI** version to a more recent one, and make sure that all your code is working correctly by running your tests.

[deployment/versions.md › About FastAPI versions > About versions](https://fastapi.tiangolo.com/deployment/versions/)

> Breaking changes and new features are added in "MINOR" versions.

*Respuesta esperada:* Before upgrading to a newer minor version, which may introduce breaking changes, you should first add and run tests for your application to ensure your code continues to work correctly.

---

### q063 · multi · es

**¿En qué versiones específicas de FastAPI se introdujo el comportamiento donde el código de salida tras un yield se ejecuta después de enviar la respuesta, y cuándo se añadió el soporte de ámbitos para controlar este momento exacto de ejecución?**

[advanced/advanced-dependencies.md › Advanced Dependencies > Dependencies with `yield`, `HTTPException`, `except` and Background Tasks > Dependencies with `yield` and `StreamingResponse`, Technical Details](https://fastapi.tiangolo.com/advanced/advanced-dependencies/)

> This behavior was reverted in 0.118.0, to make the exit code after `yield` be executed after the response is sent.

[advanced/advanced-dependencies.md › Advanced Dependencies > Dependencies with `yield`, `HTTPException`, `except` and Background Tasks > Dependencies with `yield` and `scope`](https://fastapi.tiangolo.com/advanced/advanced-dependencies/)

> In version 0.121.0, FastAPI added support for `Depends(scope="function")` for dependencies with `yield`.

*Respuesta esperada:* El comportamiento para que el código de salida tras un yield se ejecute después de enviar la respuesta se revirtió en la versión 0.118.0. Posteriormente, en la versión 0.121.0 se añadió soporte para `Depends(scope="function")`, permitiendo que el código de salida se ejecute justo al terminar la función de operación de ruta, antes de enviar la respuesta.

---

### q064 · multi · en

**How do I handle multiple file uploads efficiently using spooled temporary files in my endpoints?**

[tutorial/request-files.md › Request Files > File Parameters with `UploadFile`](https://fastapi.tiangolo.com/tutorial/request-files/)

> It uses a "spooled" file:

[tutorial/request-files.md › Request Files > Multiple File Uploads](https://fastapi.tiangolo.com/tutorial/request-files/)

> To use that, declare a list of `bytes` or `UploadFile`:

*Respuesta esperada:* You can handle multiple file uploads efficiently by declaring a list of UploadFile parameters in your path operation function. This leverages spooled files that store data in memory up to a limit and then spill over to disk, preventing memory exhaustion when handling multiple large files simultaneously.

---

### q065 · multi · es

**Qu debo hacer para generar un diccionario solo con los datos que el usuario realmente envio y cuáles son los pasos generales de una actualización parcial?**

[tutorial/body-updates.md › Body - Updates > Partial updates with `PATCH` > Partial updates recap](https://fastapi.tiangolo.com/tutorial/body-updates/)

> Generate a `dict` without default values from the input model (using `exclude_unset`).

[tutorial/body-updates.md › Body - Updates > Partial updates with `PATCH` > Using Pydantic's `exclude_unset` parameter](https://fastapi.tiangolo.com/tutorial/body-updates/)

> If you want to receive partial updates, it's very useful to use the parameter `exclude_unset` in Pydantic's model's `.model_dump()`.

*Respuesta esperada:* Para hacer una actualización parcial, debes utilizar el parámetro exclude_unset=True con el método model_dump() del modelo. Este es uno de los pasos clave para evitar sobrescribir datos con valores predeterminadas del modelo.

---

### q066 · multi · en

**Which HTTP methods should I use when sending a body to my API, and how does FastAPI identify that parameter as a body rather than a path or query parameter?**

[tutorial/body.md › Request Body](https://fastapi.tiangolo.com/tutorial/body/)

> To send data, you should use one of: POST (the most common), PUT, DELETE or PATCH.

[tutorial/body.md › Request Body > Request body + path + query parameters](https://fastapi.tiangolo.com/tutorial/body/)

> If the parameter is declared to be of the type of a Pydantic model, it will be interpreted as a request body.

*Respuesta esperada:* You should use POST, PUT, DELETE, or PATCH methods when sending data in a request body. FastAPI will automatically interpret a function parameter as a request body if its type is declared as a Pydantic model.

---

### q068 · multi · en

**How can I define a custom streaming response class specifically for PNG images, and how is the image data handled in memory to allow iteration?**

[advanced/stream-data.md › Stream Data > A Custom `PNGStreamingResponse`](https://fastapi.tiangolo.com/advanced/stream-data/)

> You can create a custom sub-class of StreamingResponse that sets the Content-Type header to the type of data you're streaming.

[advanced/stream-data.md › Stream Data > A Custom `PNGStreamingResponse` > Simulate a File](https://fastapi.tiangolo.com/advanced/stream-data/)

> In this example, we are simulating a file with io.BytesIO, which is a file-like object that lives only in memory, but lets us use the same interface.

*Respuesta esperada:* You can create a custom subclass of StreamingResponse where you set the media_type attribute to image/png. To supply the data, you can simulate a file using io.BytesIO in memory, allowing you to iterate over its contents just like a real file.

---

### q069 · unanswerable · es

**¿Cuál es la forma recomendada de integrar Supabase Auth para validar tokens JWT en una API de FastAPI?**

---

### q070 · unanswerable · es

**¿Cómo puedo enviar eventos en tiempo real hacia un canal de Pusher desde mis rutas en FastAPI?**

---

### q071 · unanswerable · en

**What is the recommended approach to send push notifications via Firebase Cloud Messaging inside a FastAPI endpoint?**

---

### q072 · unanswerable · en

**How can I integrate Stripe webhooks to process card payments in a FastAPI application?**

---

### q073 · unanswerable · en

**How do I configure Datadog APM tracing for incoming requests in a FastAPI application?**

---

### q075 · multi · en

**How does Docker's layer caching mechanism affect the build time, and what determines how long a container stays running?**

[deployment/docker.md › FastAPI in Containers - Docker > Build a Docker Image for FastAPI > Dockerfile > Docker Cache](https://fastapi.tiangolo.com/deployment/docker/)

> Downloading and installing the package dependencies could take minutes, but using the cache would take seconds at most.

[deployment/docker.md › FastAPI in Containers - Docker > Containers and Processes](https://fastapi.tiangolo.com/deployment/docker/)

> A container is running as long as the main process (command or program) is running.

*Respuesta esperada:* Docker's layer caching reduces build times from minutes down to seconds by reusing previously built layers when files like requirements.txt remain unchanged. Meanwhile, a container remains running as long as its main process is active, and the container will stop if that main process stops.

---

### q076 · multi · en

**What is the general goal of putting a web API on a remote server, and what are some ways to accomplish this setup?**

[deployment/index.md › Deployment > What Does Deployment Mean](https://fastapi.tiangolo.com/deployment/)

> To deploy an application means to perform the necessary steps to make it available to the users.

[deployment/index.md › Deployment > Deployment Strategies](https://fastapi.tiangolo.com/deployment/)

> You could deploy a server yourself using a combination of tools, you could use a cloud service that does part of the work for you, or other possible options.

*Respuesta esperada:* Deploying an application means making it accessible to users efficiently by placing it on a remote machine running a high-performance server program. To achieve this, you can either configure and deploy a server yourself using various tools, or rely on a cloud service like FastAPI Cloud to handle part of the process.

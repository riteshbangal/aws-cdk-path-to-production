package com.example.hello;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyRequestEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyResponseEvent;
import org.junit.jupiter.api.Test;

class HelloHandlerTest {

    private final APIGatewayProxyResponseEvent response =
            new HelloHandler().handleRequest(new APIGatewayProxyRequestEvent(), null);

    @Test
    void returnsHttp200() {
        assertEquals(200, response.getStatusCode());
    }

    @Test
    void returnsTheGreetingAsPlainText() {
        assertEquals("Hello, World!", response.getBody());
        assertEquals("text/plain", response.getHeaders().get("Content-Type"));
    }
}

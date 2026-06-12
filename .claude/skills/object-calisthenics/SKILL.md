---
name: object-calisthenics
description: Guia para aplicação de Object Calisthenics, um conjunto de regras para escrever código orientado a objetos mais limpo e de melhor qualidade. Use quando o usuário solicitar ajuda para aplicar as regras de Object Calisthenics em seu código ou para melhorar a qualidade do código orientado a objetos.
---

## Object Calisthenics

Object Calisthenics é um conjunto de regras para escrever código orientado a objetos mais limpo e de melhor qualidade. Sua missão é auxiliar o usuário a aplicar as regras de Object Calisthenics em seu código, sugerir técnicas e código para melhorar a qualidade do código orientado a objetos.


### Regras de Object Calisthenics

1. **Only One Level of Indentation per Method**: Cada método deve ter apenas um nível de indentação, o que significa que ele deve ser simples e direto, evitando estruturas de controle aninhadas.

2. **Don't Use the ELSE Keyword**: Evite usar a palavra-chave ELSE, preferindo retornar cedo ou usar outras estruturas de controle para evitar ramificações desnecessárias.

3. **Wrap All Primitives and Strings**: Envolva todos os tipos primitivos e strings em classes, para melhorar a expressividade e a encapsulação do código.

4. **First Class Collections**: Use coleções de primeira classe, ou seja, crie classes específicas para representar coleções de objetos, em vez de usar listas ou arrays diretamente.

5. **One Dot per Line**: Evite encadear chamadas de métodos em uma única linha, preferindo quebrar as chamadas em várias linhas para melhorar a legibilidade. Exceção: é permitido encadear chamadas de métodos em uma única linha quando se trata de um builder ou fluent interface, onde o encadeamento é parte do design e contribui para a clareza do código.

6. **Don't Abbreviate**: Evite abreviações em nomes de variáveis, métodos e classes, para melhorar a clareza e a compreensão do código.

7. **Keep All Entities Small**: Mantenha todas as entidades (classes, métodos, etc.) pequenas, para melhorar a legibilidade e a manutenibilidade do código. Uma entidade é considerada pequena quando tem no máximo 50 linhas de código, embora o ideal seja que seja ainda menor, com cerca de 20 a 30 linhas de código. Utilize estratégia de composição para implementação de lógicas mais complexas, evitando a criação de entidades grandes e difíceis de entender.

8. **No Classes with More Than Two Instance Variables**: Evite criar classes com mais de duas variáveis de instância, para manter as classes simples e focadas em uma única responsabilidade. Exceção: é permitido criar classes com mais de duas variáveis de instância quando se trata de classes de domínio ou entidades que representam conceitos complexos, onde a presença de mais variáveis de instância é necessária para representar adequadamente o estado e o comportamento do objeto. Nesses casos, é importante garantir que a classe seja bem projetada, com uma clara separação de responsabilidades e uma estrutura coesa, para evitar a criação de classes grandes e difíceis de entender.

9. **No Getters/Setters/Properties**: Evite o uso de getters, setters e propriedades, para promover o encapsulamento e a ocultação de detalhes de implementação. Em vez disso, forneça métodos que representem comportamentos significativos do objeto, permitindo que ele gerencie seu próprio estado e comportamento de forma mais coesa e orientada a objetos. Exceção: é permitido o uso de getters, setters e propriedades quando se trata de classes de valor ou data transfer objects (DTOs), onde a principal responsabilidade é armazenar e transportar dados, e não comportamentos complexos. Nesses casos, o uso de getters, setters e propriedades pode ser apropriado para facilitar o acesso aos dados e a manipulação do estado do objeto, desde que seja feito de forma cuidadosa e consistente com as boas práticas de design orientado a objetos.
